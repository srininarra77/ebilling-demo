# ============================================================
# E-BILLING SYSTEM - AGENT 2: Invoice Verification
# ============================================================
#
# PURPOSE:
# Process invoices from the AP inbox, verify rates and hours
# against vendor contracts, and approve or flag discrepancies.
#
# WORKFLOW:
# 1. Read invoices from inbox (simulated email)
# 2. Look up vendor in database (from Agent 1)
# 3. Verify rates match contracted rates
# 4. Check for any red flags (excessive hours, etc.)
# 5. Approve or reject with reasons
# 6. Notify Accounts Payable
#
# RUN: python3 agent_2_invoice_verification.py
#
# PREREQUISITE: Run agent_1_vendor_onboarding.py first to 
#               create the vendor database!
# ============================================================

from crewai import Agent, Task, Crew
from crewai.tools import tool
from langchain_anthropic import ChatAnthropic
import json
import os
from datetime import datetime

llm = ChatAnthropic(model="claude-sonnet-4-20250514")


# ============================================================
# PATHS
# ============================================================

VENDOR_DB_PATH = "vendor_database.json"
INBOX_PATH = "inbox/invoices.json"
PROCESSED_PATH = "processed_invoices.json"
AP_NOTIFICATIONS_PATH = "ap_notifications.json"


# ============================================================
# TOOL 1: Read Invoices from Inbox
# ============================================================

@tool
def read_invoices_from_inbox() -> str:
    """
    Read pending invoices from the Accounts Payable inbox.
    These are invoices submitted by law firms awaiting verification.
    
    Returns:
        JSON with list of invoices to process
    """
    try:
        if not os.path.exists(INBOX_PATH):
            return json.dumps({"error": "No invoices in inbox", "invoices": []})
        
        with open(INBOX_PATH, 'r') as f:
            invoices = json.load(f)
        
        return json.dumps({
            "invoice_count": len(invoices),
            "invoices": invoices
        }, indent=2)
    
    except Exception as e:
        return json.dumps({"error": str(e)})


# ============================================================
# TOOL 2: Look Up Vendor Rates
# ============================================================

@tool
def lookup_vendor_rates(firm_name: str) -> str:
    """
    Look up contracted rates for a law firm from the vendor database.
    Use this to compare invoice rates against what we agreed to pay.
    
    Args:
        firm_name: The name of the law firm (e.g., "Baker & Sterling LLP")
    
    Returns:
        JSON with vendor details including contracted rates and status
    """
    try:
        if not os.path.exists(VENDOR_DB_PATH):
            return json.dumps({
                "error": "Vendor database not found. Run Agent 1 first.",
                "found": False
            })
        
        with open(VENDOR_DB_PATH, 'r') as f:
            db = json.load(f)
        
        # Search for vendor (case-insensitive partial match)
        firm_lower = firm_name.lower()
        for vendor in db["vendors"]:
            if firm_lower in vendor["firm_name"].lower():
                return json.dumps({
                    "found": True,
                    "vendor_id": vendor["vendor_id"],
                    "firm_name": vendor["firm_name"],
                    "status": vendor["status"],
                    "contracted_rates": {
                        "partner": float(vendor["partner_rate"]),
                        "associate": float(vendor["associate_rate"]),
                        "paralegal": float(vendor["paralegal_rate"])
                    },
                    "payment_terms": vendor["payment_terms"]
                }, indent=2)
        
        return json.dumps({
            "found": False,
            "error": f"Vendor '{firm_name}' not found in database"
        })
    
    except Exception as e:
        return json.dumps({"error": str(e), "found": False})


# ============================================================
# TOOL 3: Verify Invoice
# ============================================================

@tool
def verify_invoice(invoice_json: str, vendor_rates_json: str) -> str:
    """
    Verify an invoice against contracted vendor rates.
    Checks each line item for rate compliance and flags discrepancies.
    
    Args:
        invoice_json: JSON string of the invoice to verify
        vendor_rates_json: JSON string of vendor's contracted rates
    
    Returns:
        Verification result with any discrepancies found
    """
    try:
        invoice = json.loads(invoice_json)
        vendor = json.loads(vendor_rates_json)
        
        if not vendor.get("found"):
            return json.dumps({
                "invoice_id": invoice.get("invoice_id"),
                "status": "REJECTED",
                "reason": "Vendor not found in database"
            })
        
        # Check if vendor is active
        if vendor.get("status") == "inactive":
            return json.dumps({
                "invoice_id": invoice.get("invoice_id"),
                "firm_name": invoice.get("firm_name"),
                "status": "REJECTED",
                "reason": f"Vendor '{invoice.get('firm_name')}' is INACTIVE. Cannot process invoices from inactive vendors."
            })
        
        discrepancies = []
        warnings = []
        total_overcharge = 0
        
        contracted = vendor.get("contracted_rates", {})
        
        for item in invoice.get("line_items", []):
            level = item.get("level", "").lower()
            billed_rate = float(item.get("rate", 0))
            contracted_rate = contracted.get(level, 0)
            
            # Check rate
            if billed_rate > contracted_rate:
                overcharge = (billed_rate - contracted_rate) * item.get("hours", 0)
                total_overcharge += overcharge
                discrepancies.append({
                    "timekeeper": item.get("timekeeper"),
                    "level": level,
                    "issue": "RATE EXCEEDS CONTRACT",
                    "billed_rate": billed_rate,
                    "contracted_rate": contracted_rate,
                    "hours": item.get("hours"),
                    "overcharge_amount": overcharge
                })
            
            # Check for excessive hours (warning only)
            hours = item.get("hours", 0)
            if hours > 10 and level == "partner":
                warnings.append({
                    "timekeeper": item.get("timekeeper"),
                    "issue": f"High partner hours ({hours}hrs) - consider reviewing"
                })
            if hours > 20:
                warnings.append({
                    "timekeeper": item.get("timekeeper"),
                    "issue": f"Excessive hours ({hours}hrs) on single invoice - consider reviewing"
                })
        
        # Determine status
        if discrepancies:
            status = "FLAGGED"
            recommendation = f"Invoice has rate discrepancies totaling ${total_overcharge:.2f}. Request corrected invoice or approve adjusted amount."
        else:
            status = "APPROVED"
            recommendation = "Invoice verified. Rates match contract. Clear for payment."
        
        return json.dumps({
            "invoice_id": invoice.get("invoice_id"),
            "firm_name": invoice.get("firm_name"),
            "matter": invoice.get("matter"),
            "invoice_amount": invoice.get("total_amount"),
            "status": status,
            "discrepancies": discrepancies,
            "total_overcharge": total_overcharge,
            "warnings": warnings,
            "recommendation": recommendation
        }, indent=2)
    
    except Exception as e:
        return json.dumps({"error": str(e), "status": "ERROR"})


# ============================================================
# TOOL 4: Send AP Notification
# ============================================================

@tool
def send_ap_notification(verification_result_json: str) -> str:
    """
    Send notification to Accounts Payable with invoice decision.
    Use this after verifying an invoice to notify AP of the result.
    
    Args:
        verification_result_json: JSON with verification result and decision
    
    Returns:
        Confirmation that AP was notified
    """
    try:
        result = json.loads(verification_result_json)
        
        # Load existing notifications or create new
        if os.path.exists(AP_NOTIFICATIONS_PATH):
            with open(AP_NOTIFICATIONS_PATH, 'r') as f:
                notifications = json.load(f)
        else:
            notifications = {"notifications": []}
        
        # Create notification
        notification = {
            "notification_id": f"AP-{len(notifications['notifications']) + 1:04d}",
            "timestamp": datetime.now().isoformat(),
            "invoice_id": result.get("invoice_id"),
            "firm_name": result.get("firm_name"),
            "amount": result.get("invoice_amount"),
            "status": result.get("status"),
            "action_required": "RELEASE_PAYMENT" if result.get("status") == "APPROVED" else "HOLD_PAYMENT",
            "details": result.get("recommendation"),
            "discrepancies": result.get("discrepancies", []),
            "total_overcharge": result.get("total_overcharge", 0)
        }
        
        notifications["notifications"].append(notification)
        
        # Save notifications
        with open(AP_NOTIFICATIONS_PATH, 'w') as f:
            json.dump(notifications, f, indent=2)
        
        # Format message based on status
        if result.get("status") == "APPROVED":
            message = f"✅ APPROVED: Invoice {result.get('invoice_id')} from {result.get('firm_name')} for ${result.get('invoice_amount'):,.2f} - RELEASE PAYMENT"
        elif result.get("status") == "FLAGGED":
            message = f"⚠️ FLAGGED: Invoice {result.get('invoice_id')} from {result.get('firm_name')} - HOLD PAYMENT - Overcharge of ${result.get('total_overcharge'):,.2f} detected"
        else:
            message = f"❌ REJECTED: Invoice {result.get('invoice_id')} from {result.get('firm_name')} - {result.get('recommendation')}"
        
        return json.dumps({
            "notification_sent": True,
            "notification_id": notification["notification_id"],
            "message": message
        }, indent=2)
    
    except Exception as e:
        return json.dumps({"notification_sent": False, "error": str(e)})


# ============================================================
# AGENT: Invoice Verification Specialist
# ============================================================

invoice_verification_agent = Agent(
    role="Invoice Verification Specialist",
    
    goal="Verify law firm invoices against contracted rates and approve or flag for AP",
    
    backstory="""You are an experienced accounts payable analyst specializing 
    in legal invoices. You meticulously verify every invoice against contracted 
    rates before approving payment. You catch billing errors that save the 
    company thousands of dollars. You know that:
    - Rates must match the contracted amounts exactly
    - Inactive vendors cannot submit invoices
    - Excessive hours should be flagged for review
    You always notify AP with clear decisions and explanations.""",
    
    tools=[
        read_invoices_from_inbox,
        lookup_vendor_rates,
        verify_invoice,
        send_ap_notification
    ],
    
    llm=llm,
    verbose=True
)


# ============================================================
# TASK: Process All Invoices
# ============================================================

verification_task = Task(
    description="""
    Process all invoices in the AP inbox.
    
    For EACH invoice:
    1. Read the invoice details
    2. Use lookup_vendor_rates to get the firm's contracted rates
    3. Use verify_invoice to compare billed rates vs contracted rates
    4. Use send_ap_notification to notify AP of the decision
    
    After processing all invoices, provide a summary:
    - Total invoices processed
    - Approved (ready for payment)
    - Flagged (need review/correction)
    - Rejected (cannot process)
    - Total dollar amount approved
    - Total overcharges detected
    """,
    
    expected_output="""Summary report with:
    - Count and details of each invoice processed
    - Clear APPROVED/FLAGGED/REJECTED status for each
    - Total amounts approved for payment
    - Any discrepancies found with dollar amounts""",
    
    agent=invoice_verification_agent
)


# ============================================================
# CREW
# ============================================================

crew = Crew(
    agents=[invoice_verification_agent],
    tasks=[verification_task],
    verbose=True
)


# ============================================================
# RUN
# ============================================================

if __name__ == "__main__":
    print("="*60)
    print("E-BILLING SYSTEM - Agent 2: Invoice Verification")
    print("="*60)
    
    # Check prerequisites
    if not os.path.exists(VENDOR_DB_PATH):
        print("\n❌ ERROR: Vendor database not found!")
        print("   Please run agent_1_vendor_onboarding.py first.")
        print("="*60)
        exit(1)
    
    if not os.path.exists(INBOX_PATH):
        print("\n❌ ERROR: No invoices found in inbox!")
        print(f"   Expected: {INBOX_PATH}")
        print("="*60)
        exit(1)
    
    print("\nThis agent will:")
    print("1. Read invoices from AP inbox")
    print("2. Look up vendor contracted rates")
    print("3. Verify each invoice")
    print("4. Notify AP of decisions")
    print("="*60 + "\n")
    
    # Clean up previous notifications for fresh demo
    if os.path.exists(AP_NOTIFICATIONS_PATH):
        os.remove(AP_NOTIFICATIONS_PATH)
    
    result = crew.kickoff()
    
    print("\n" + "="*60)
    print("VERIFICATION COMPLETE")
    print("="*60)
    print(result)
    
    # Show AP notifications
    print("\n" + "="*60)
    print("AP NOTIFICATIONS SENT:")
    print("="*60)
    if os.path.exists(AP_NOTIFICATIONS_PATH):
        with open(AP_NOTIFICATIONS_PATH, 'r') as f:
            notifications = json.load(f)
            for n in notifications["notifications"]:
                status_icon = "✅" if n["action_required"] == "RELEASE_PAYMENT" else "⚠️" if n["status"] == "FLAGGED" else "❌"
                print(f"\n{status_icon} {n['notification_id']}")
                print(f"   Invoice: {n['invoice_id']} | {n['firm_name']}")
                print(f"   Amount: ${n['amount']:,.2f}")
                print(f"   Action: {n['action_required']}")
                if n.get("total_overcharge", 0) > 0:
                    print(f"   Overcharge: ${n['total_overcharge']:,.2f}")


# ============================================================
# EXPECTED ISSUES AGENT SHOULD CATCH:
# ============================================================
#
# INV-2025-002 (Goldman Hart):
#   - Partner rate $750 vs contracted $700 = OVERCHARGE
#
# INV-2025-004 (Fitzgerald & Moore):
#   - Vendor is INACTIVE = REJECTED
#
# INV-2025-005 (Baker & Sterling):
#   - Partner rate $700 vs contracted $650 = OVERCHARGE
#
# All other invoices should be APPROVED
# ============================================================


# ============================================================
# KEY CONCEPTS IN THIS LESSON:
# ============================================================
#
# 1. READING FROM PREVIOUS AGENT'S OUTPUT:
#    Agent 2 reads vendor_database.json created by Agent 1
#
# 2. MULTIPLE TOOLS WORKING TOGETHER:
#    read → lookup → verify → notify
#
# 3. BUSINESS LOGIC IN TOOLS:
#    - Rate comparison
#    - Status checking (active/inactive)
#    - Overcharge calculation
#
# 4. OUTPUT FOR NEXT STEP:
#    Creates ap_notifications.json for AP team
#
# NEXT: Agent 3 - Payment Processing or Reporting
# ============================================================
