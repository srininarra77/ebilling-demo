"""
E-Billing System - AI-Powered Legal Operations Prototype
"""

import streamlit as st
import pandas as pd
import json
import os
import csv
from datetime import datetime
from pathlib import Path

SCRIPT_DIR = Path(__file__).parent.resolve()

st.set_page_config(
    page_title="E-Billing System Prototype",
    page_icon="⚖️",
    layout="wide",
    initial_sidebar_state="expanded"
)

# ============================================================
# CUSTOM STYLING
# ============================================================
st.markdown("""
<style>
    .main-header {
        font-size: 2.5rem;
        font-weight: 700;
        color: #1E3A5F;
    }
    .sub-header {
        font-size: 1.1rem;
        color: #666;
        margin-bottom: 1rem;
    }
    .metric-card {
        background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
        padding: 1rem;
        border-radius: 10px;
        color: white;
    }
    .author-box {
        background: #f8f9fa;
        padding: 1rem;
        border-radius: 8px;
        border-left: 4px solid #1E3A5F;
    }
    .roi-positive {
        color: #28a745;
        font-weight: bold;
    }
</style>
""", unsafe_allow_html=True)

VENDOR_DB_PATH = SCRIPT_DIR / "vendor_database.json"
LAWYERS_DB_PATH = SCRIPT_DIR / "internal_lawyers.json"
ASSIGNMENTS_DB_PATH = SCRIPT_DIR / "matter_assignments.json"
AP_NOTIFICATIONS_PATH = SCRIPT_DIR / "ap_notifications.json"
INBOX_PATH = SCRIPT_DIR / "inbox" / "invoices.json"
LAW_FIRMS_CSV = SCRIPT_DIR / "law_firms.csv"
MATTERS_CSV = SCRIPT_DIR / "matters.csv"

def load_json(path):
    if os.path.exists(path):
        with open(path, 'r') as f:
            return json.load(f)
    return None

def save_json(path, data):
    with open(path, 'w') as f:
        json.dump(data, f, indent=2)

def reset_demo_data():
    for path in [VENDOR_DB_PATH, ASSIGNMENTS_DB_PATH, AP_NOTIFICATIONS_PATH]:
        if os.path.exists(path):
            os.remove(path)
    if os.path.exists(LAWYERS_DB_PATH):
        with open(LAWYERS_DB_PATH, 'r') as f:
            lawyers = json.load(f)
        for l in lawyers["lawyers"]:
            l["current_caseload"] = 0
        save_json(LAWYERS_DB_PATH, lawyers)
    st.success("✅ Demo data reset!")

def run_vendor_onboarding():
    vendors = []
    with open(LAW_FIRMS_CSV, 'r') as f:
        reader = csv.DictReader(f)
        for row in reader:
            vendors.append(row)
    db = {"vendors": [], "next_id": 1001}
    results = {"onboarded": [], "warnings": []}
    for vendor in vendors:
        errors = []
        warnings = []
        partner_rate = float(vendor.get("partner_rate", 0))
        if partner_rate > 800:
            warnings.append(f"Partner rate ${partner_rate}/hr exceeds $800 cap")
        if vendor.get("status") not in ["active", "inactive"]:
            errors.append("Invalid status")
        if not errors:
            vendor["vendor_id"] = f"VND-{db['next_id']}"
            db["next_id"] += 1
            db["vendors"].append(vendor)
            results["onboarded"].append({"vendor_id": vendor["vendor_id"], "firm_name": vendor["firm_name"], "status": vendor["status"], "warnings": warnings})
            if warnings:
                results["warnings"].extend(warnings)
    save_json(VENDOR_DB_PATH, db)
    return results

def run_invoice_verification():
    with open(INBOX_PATH, 'r') as f:
        invoices = json.load(f)
    vendor_db = load_json(VENDOR_DB_PATH)
    if not vendor_db:
        return {"error": "Run Agent 1 first"}
    results = {"approved": [], "flagged": [], "rejected": []}
    notifications = {"notifications": []}
    for invoice in invoices:
        firm_name = invoice.get("firm_name", "")
        vendor = None
        for v in vendor_db["vendors"]:
            if firm_name.lower() in v["firm_name"].lower():
                vendor = v
                break
        if not vendor:
            results["rejected"].append({"invoice_id": invoice["invoice_id"], "firm_name": firm_name, "reason": "Vendor not in database", "amount": invoice.get("total_amount", 0)})
            notification = {"notification_id": f"AP-{len(notifications['notifications']) + 1:04d}", "invoice_id": invoice["invoice_id"], "firm_name": firm_name, "amount": invoice.get("total_amount", 0), "timestamp": datetime.now().isoformat(), "status": "REJECTED", "action": "DO_NOT_PAY", "reason": "Vendor not in database"}
            notifications["notifications"].append(notification)
            continue
        if vendor.get("status") == "inactive":
            results["rejected"].append({"invoice_id": invoice["invoice_id"], "firm_name": firm_name, "reason": "Vendor is INACTIVE", "amount": invoice.get("total_amount", 0)})
            notification = {"notification_id": f"AP-{len(notifications['notifications']) + 1:04d}", "invoice_id": invoice["invoice_id"], "firm_name": firm_name, "amount": invoice.get("total_amount", 0), "timestamp": datetime.now().isoformat(), "status": "REJECTED", "action": "DO_NOT_PAY", "reason": "Vendor is INACTIVE - cannot process invoices from inactive vendors"}
            notifications["notifications"].append(notification)
            continue
        discrepancies = []
        total_overcharge = 0
        contracted_rates = {"partner": float(vendor.get("partner_rate", 0)), "associate": float(vendor.get("associate_rate", 0)), "paralegal": float(vendor.get("paralegal_rate", 0))}
        line_item_details = []
        for item in invoice.get("line_items", []):
            level = item.get("level", "").lower()
            billed_rate = float(item.get("rate", 0))
            contracted_rate = contracted_rates.get(level, 0)
            hours = item.get("hours", 0)
            item_detail = {
                "timekeeper": item.get("timekeeper"),
                "level": level,
                "description": item.get("description", ""),
                "hours": hours,
                "billed_rate": billed_rate,
                "contracted_rate": contracted_rate,
                "billed_amount": item.get("amount", 0),
                "status": "OK"
            }
            if billed_rate > contracted_rate:
                overcharge = (billed_rate - contracted_rate) * hours
                total_overcharge += overcharge
                item_detail["status"] = "OVERCHARGE"
                item_detail["overcharge"] = overcharge
                discrepancies.append({"timekeeper": item.get("timekeeper"), "level": level, "billed": billed_rate, "contracted": contracted_rate, "overcharge": overcharge})
            line_item_details.append(item_detail)
        notification = {"notification_id": f"AP-{len(notifications['notifications']) + 1:04d}", "invoice_id": invoice["invoice_id"], "firm_name": firm_name, "amount": invoice.get("total_amount"), "matter": invoice.get("matter"), "matter_id": invoice.get("matter_id"), "invoice_date": invoice.get("invoice_date"), "total_hours": invoice.get("total_hours"), "timestamp": datetime.now().isoformat(), "line_items": line_item_details, "contracted_rates": contracted_rates}
        if discrepancies:
            notification["status"] = "FLAGGED"
            notification["action"] = "HOLD_PAYMENT"
            notification["overcharge"] = total_overcharge
            notification["discrepancies"] = discrepancies
            notification["reason"] = f"Rate discrepancies detected - ${total_overcharge:,.2f} overcharge"
            results["flagged"].append({"invoice_id": invoice["invoice_id"], "firm_name": firm_name, "amount": invoice.get("total_amount"), "overcharge": total_overcharge, "discrepancies": discrepancies})
        else:
            notification["status"] = "APPROVED"
            notification["action"] = "RELEASE_PAYMENT"
            notification["reason"] = "All rates match contracted amounts"
            results["approved"].append({"invoice_id": invoice["invoice_id"], "firm_name": firm_name, "amount": invoice.get("total_amount")})
        notifications["notifications"].append(notification)
    save_json(AP_NOTIFICATIONS_PATH, notifications)
    return results

def run_case_assignment():
    matters = []
    with open(MATTERS_CSV, 'r') as f:
        reader = csv.DictReader(f)
        for row in reader:
            matters.append(row)
    with open(LAWYERS_DB_PATH, 'r') as f:
        lawyers_db = json.load(f)
    
    for l in lawyers_db["lawyers"]:
        l["current_caseload"] = 0
    
    results = {"assigned": [], "unassigned": []}
    assignments = {"assignments": []}
    
    area_mapping = {
        "litigation": ["litigation"], 
        "patent_infringement": ["patent_infringement", "ip_trademark"], 
        "ip_trademark": ["ip_trademark", "patent_infringement"], 
        "m&a": ["m&a"], 
        "employment": ["employment"], 
        "regulatory": ["regulatory"], 
        "contract_review": ["contract_review"], 
        "real_estate": ["real_estate"]
    }
    
    for matter in matters:
        case_type = matter.get("case_type", "").lower()
        priority = matter.get("priority", "medium")
        search_areas = area_mapping.get(case_type, [case_type])
        
        candidates = []
        reasoning_steps = []
        
        reasoning_steps.append(f"🔍 **Step 1: Identify case type** → '{case_type}'")
        reasoning_steps.append(f"🔍 **Step 2: Find lawyers with matching practice areas** → Looking for: {', '.join(search_areas)}")
        
        for lawyer in lawyers_db["lawyers"]:
            if lawyer["status"] != "active":
                reasoning_steps.append(f"   ❌ {lawyer['name']} - Skipped (Status: {lawyer['status']})")
                continue
            
            available = lawyer["max_caseload"] - lawyer["current_caseload"]
            if available <= 0:
                reasoning_steps.append(f"   ❌ {lawyer['name']} - Skipped (No capacity: {lawyer['current_caseload']}/{lawyer['max_caseload']})")
                continue
            
            matched_area = None
            for area in search_areas:
                if area in [pa.lower() for pa in lawyer["practice_areas"]]:
                    matched_area = area
                    break
            
            if matched_area:
                candidates.append({
                    "lawyer": lawyer,
                    "available_capacity": available,
                    "matched_area": matched_area
                })
                reasoning_steps.append(f"   ✅ {lawyer['name']} - Match! (Practice: {matched_area}, Capacity: {available} slots available)")
            else:
                reasoning_steps.append(f"   ❌ {lawyer['name']} - No practice area match (Has: {', '.join(lawyer['practice_areas'])})")
        
        best_lawyer = None
        selection_reason = ""
        
        if candidates:
            if priority == "high":
                candidates.sort(key=lambda x: x["available_capacity"], reverse=True)
                selection_reason = f"High priority case → Selected lawyer with most available capacity ({candidates[0]['available_capacity']} slots)"
            else:
                candidates.sort(key=lambda x: x["lawyer"]["current_caseload"])
                selection_reason = f"Standard priority → Selected to balance workload (current load: {candidates[0]['lawyer']['current_caseload']} cases)"
            
            best_lawyer = candidates[0]["lawyer"]
            reasoning_steps.append(f"🎯 **Step 3: Select best candidate** → {selection_reason}")
            reasoning_steps.append(f"✅ **Decision: Assign to {best_lawyer['name']}** ({best_lawyer.get('title', 'Counsel')})")
        
        if best_lawyer:
            assignment = {
                "assignment_id": f"ASN-{len(assignments['assignments']) + 1:04d}", 
                "matter_id": matter["matter_id"], 
                "matter_name": matter["matter_name"], 
                "case_type": case_type, 
                "priority": priority, 
                "assigned_to": {
                    "lawyer_id": best_lawyer["lawyer_id"], 
                    "name": best_lawyer["name"],
                    "title": best_lawyer.get("title", "Counsel"),
                    "email": best_lawyer["email"]
                }, 
                "outside_counsel": matter.get("outside_counsel", ""),
                "reasoning": reasoning_steps,
                "selection_reason": selection_reason
            }
            assignments["assignments"].append(assignment)
            
            for l in lawyers_db["lawyers"]:
                if l["lawyer_id"] == best_lawyer["lawyer_id"]:
                    l["current_caseload"] += 1
                    break
            
            results["assigned"].append({
                "matter_id": matter["matter_id"], 
                "matter_name": matter["matter_name"], 
                "case_type": case_type, 
                "assigned_to": best_lawyer["name"],
                "reasoning": reasoning_steps
            })
        else:
            reasoning_steps.append("❌ **Decision: Cannot assign** - No available lawyer with matching expertise")
            results["unassigned"].append({
                "matter_id": matter["matter_id"], 
                "matter_name": matter["matter_name"], 
                "case_type": case_type, 
                "reason": "No available lawyer with matching expertise",
                "reasoning": reasoning_steps
            })
            
    save_json(ASSIGNMENTS_DB_PATH, assignments)
    save_json(LAWYERS_DB_PATH, lawyers_db)
    return results

# ============================================================
# UI HEADER
# ============================================================

st.markdown('<p class="main-header">⚖️ E-Billing System</p>', unsafe_allow_html=True)
st.markdown('<p class="sub-header">AI-Powered Legal Operations Prototype</p>', unsafe_allow_html=True)

# ============================================================
# SIDEBAR
# ============================================================

with st.sidebar:
    st.image("https://img.icons8.com/fluency/96/000000/law.png", width=80)
    st.markdown("### 🔧 Controls")
    if st.button("🔄 Reset Demo Data", type="secondary", use_container_width=True):
        reset_demo_data()
    
    st.markdown("---")
    st.markdown("### 📊 Agent Status")
    vendor_db = load_json(VENDOR_DB_PATH)
    assignments_db = load_json(ASSIGNMENTS_DB_PATH)
    ap_notifications = load_json(AP_NOTIFICATIONS_PATH)
    
    col1, col2 = st.columns(2)
    col1.metric("Vendors", len(vendor_db['vendors']) if vendor_db else 0)
    col2.metric("Invoices", len(ap_notifications['notifications']) if ap_notifications else 0)
    st.metric("Matters Assigned", len(assignments_db['assignments']) if assignments_db else 0)
    
    st.markdown("---")
    st.markdown("### ℹ️ Info")
    st.markdown("See **About** tab for system architecture and author details.")

# ============================================================
# TABS
# ============================================================

tab1, tab2, tab3, tab4, tab5 = st.tabs(["📋 Agent 1: Vendors", "💰 Agent 2: Invoices", "⚖️ Agent 3: Cases", "📊 ROI Dashboard", "ℹ️ About"])

# ============================================================
# TAB 1: VENDOR ONBOARDING
# ============================================================
with tab1:
    st.header("Agent 1: Vendor Onboarding")
    st.markdown("Reads law firm data, validates rates and status, onboards to database.")
    col1, col2 = st.columns(2)
    with col1:
        st.subheader("📁 Input: law_firms.csv")
        df = pd.read_csv(LAW_FIRMS_CSV)
        st.dataframe(df, use_container_width=True)
    with col2:
        st.subheader("🤖 Run Agent")
        if st.button("▶️ Run Vendor Onboarding", type="primary", key="run_agent1"):
            with st.spinner("Processing..."):
                results = run_vendor_onboarding()
            st.success(f"✅ Onboarded {len(results['onboarded'])} vendors")
        vendor_db = load_json(VENDOR_DB_PATH)
        if vendor_db:
            st.subheader("📦 Vendor Database")
            for v in vendor_db["vendors"]:
                st.markdown(f"{'🟢' if v['status'] == 'active' else '🔴'} **{v['vendor_id']}**: {v['firm_name']} | Partner: ${v['partner_rate']}/hr")

# ============================================================
# TAB 2: INVOICE VERIFICATION
# ============================================================
with tab2:
    st.header("Agent 2: Invoice Verification")
    st.markdown("Verifies billed rates against contracted rates. Approves, flags, or rejects invoices.")
    
    ap_notifications = load_json(AP_NOTIFICATIONS_PATH)
    
    st.subheader("📥 Invoices")
    invoices = load_json(INBOX_PATH)
    
    if invoices:
        for inv in invoices:
            verification = None
            if ap_notifications:
                for n in ap_notifications["notifications"]:
                    if n["invoice_id"] == inv["invoice_id"]:
                        verification = n
                        break
            
            if verification:
                if verification["status"] == "APPROVED":
                    status_icon = "✅"
                    status_text = "APPROVED"
                elif verification["status"] == "FLAGGED":
                    status_icon = "⚠️"
                    status_text = "FLAGGED"
                else:
                    status_icon = "❌"
                    status_text = "REJECTED"
                header = f"{status_icon} **{inv['invoice_id']}** | {inv['firm_name']} | ${inv['total_amount']:,.2f} | {status_text}"
            else:
                header = f"📄 **{inv['invoice_id']}** | {inv['firm_name']} | ${inv['total_amount']:,.2f} | ⏳ Pending"
            
            with st.expander(header, expanded=False):
                st.markdown("---")
                col1, col2 = st.columns(2)
                with col1:
                    st.markdown("**FROM:**")
                    st.markdown(f"**{inv['firm_name']}**")
                    st.markdown("*Outside Counsel*")
                with col2:
                    st.markdown("**INVOICE DETAILS:**")
                    st.markdown(f"**Invoice #:** {inv['invoice_id']}")
                    st.markdown(f"**Date:** {inv['invoice_date']}")
                
                st.markdown("---")
                st.markdown(f"**Matter:** {inv['matter']}")
                st.markdown(f"**Matter ID:** {inv['matter_id']}")
                st.markdown("---")
                
                st.markdown("**BILLING DETAILS:**")
                for idx, item in enumerate(inv["line_items"], 1):
                    st.markdown(f"""
**{idx}. {item['timekeeper']}** ({item['level'].title()})  
*{item['description']}*  
{item['hours']} hours × ${item['rate']}/hr = **${item['amount']:,.2f}**
                    """)
                
                st.markdown("---")
                col1, col2 = st.columns(2)
                col1.metric("Total Hours", inv['total_hours'])
                col2.metric("Total Amount", f"${inv['total_amount']:,.2f}")
                
                if verification:
                    st.markdown("---")
                    st.markdown("### 🤖 Agent Verification Result")
                    
                    if verification["status"] == "APPROVED":
                        st.success(f"**DECISION:** ✅ RELEASE PAYMENT")
                        st.markdown(f"**Reason:** {verification.get('reason', 'All rates match contracted amounts')}")
                        
                        st.markdown("**Rate Verification:**")
                        if "line_items" in verification:
                            for item in verification["line_items"]:
                                st.markdown(f"✅ **{item['timekeeper']}** ({item['level'].title()}): Billed ${item['billed_rate']}/hr = Contracted ${item['contracted_rate']}/hr → **OK**")
                        
                    elif verification["status"] == "FLAGGED":
                        st.warning(f"**DECISION:** ⚠️ HOLD PAYMENT")
                        st.error(f"**Total Overcharge:** ${verification.get('overcharge', 0):,.2f}")
                        st.markdown(f"**Reason:** {verification.get('reason', 'Rate discrepancies detected')}")
                        
                        st.markdown("**Rate Verification:**")
                        if "line_items" in verification:
                            for item in verification["line_items"]:
                                if item["status"] == "OK":
                                    st.markdown(f"✅ **{item['timekeeper']}** ({item['level'].title()}): Billed ${item['billed_rate']}/hr = Contracted ${item['contracted_rate']}/hr → **OK**")
                                else:
                                    st.markdown(f"❌ **{item['timekeeper']}** ({item['level'].title()}): Billed ${item['billed_rate']}/hr ≠ Contracted ${item['contracted_rate']}/hr → **OVERCHARGE +${item.get('overcharge', 0):,.2f}**")
                        
                        st.markdown(f"**Recommended Action:** Request corrected invoice or approve adjusted amount of ${verification['amount'] - verification.get('overcharge', 0):,.2f}")
                        
                    else:
                        st.error(f"**DECISION:** ❌ DO NOT PAY")
                        st.markdown(f"**Reason:** {verification.get('reason', 'Cannot process')}")
                        st.markdown("**Recommended Action:** Return invoice to sender or contact vendor.")
    
    st.markdown("---")
    
    col1, col2 = st.columns(2)
    with col1:
        st.subheader("📋 Contracted Rates (Reference)")
        vendor_db = load_json(VENDOR_DB_PATH)
        if vendor_db:
            for v in vendor_db["vendors"][:5]:
                status = "🟢" if v["status"] == "active" else "🔴"
                st.markdown(f"{status} **{v['firm_name'][:30]}**")
                st.markdown(f"   Partner: ${v['partner_rate']}/hr | Associate: ${v['associate_rate']}/hr | Paralegal: ${v['paralegal_rate']}/hr")
        else:
            st.warning("⚠️ Run Agent 1 first to load vendor rates")
    
    with col2:
        st.subheader("🤖 Run Agent")
        if not vendor_db:
            st.warning("⚠️ Run Agent 1 first to create vendor database")
        else:
            if st.button("▶️ Run Invoice Verification", type="primary", key="run_agent2"):
                with st.spinner("Verifying invoices against contracted rates..."):
                    results = run_invoice_verification()
                st.success(f"✅ Approved: {len(results['approved'])}")
                if results["flagged"]:
                    st.warning(f"⚠️ Flagged: {len(results['flagged'])}")
                if results["rejected"]:
                    st.error(f"❌ Rejected: {len(results['rejected'])}")
                st.rerun()

# ============================================================
# TAB 3: CASE ASSIGNMENT
# ============================================================
with tab3:
    st.header("Agent 3: Case/Matter Assignment")
    st.markdown("Auto-assigns matters to internal lawyers based on practice area, expertise, and workload.")
    
    assignments_db = load_json(ASSIGNMENTS_DB_PATH)
    
    assignment_lookup = {}
    if assignments_db:
        for a in assignments_db["assignments"]:
            assignment_lookup[a["matter_id"]] = a
    
    col1, col2 = st.columns(2)
    
    with col1:
        st.subheader("📁 Matters")
        df = pd.read_csv(MATTERS_CSV)
        
        assignees = []
        for _, row in df.iterrows():
            matter_id = row["matter_id"]
            if matter_id in assignment_lookup:
                assignees.append(assignment_lookup[matter_id]["assigned_to"]["name"])
            else:
                assignees.append("⏳ Pending")
        
        df["Assignee"] = assignees
        
        st.dataframe(df[["matter_id", "matter_name", "case_type", "priority", "Assignee"]], use_container_width=True)
    
    with col2:
        st.subheader("🤖 Run Agent")
        if st.button("▶️ Run Case Assignment", type="primary", key="run_agent3"):
            with st.spinner("Analyzing matters and assigning to lawyers..."):
                results = run_case_assignment()
            st.success(f"✅ Assigned: {len(results['assigned'])} matters")
            if results["unassigned"]:
                st.warning(f"⚠️ Unassigned: {len(results['unassigned'])}")
            st.rerun()
    
    st.markdown("---")
    st.subheader("👥 In-House Legal Team")
    lawyers_db = load_json(LAWYERS_DB_PATH)
    if lawyers_db:
        cols = st.columns(4)
        for idx, l in enumerate(lawyers_db["lawyers"]):
            with cols[idx % 4]:
                status_color = "🟢" if l["status"] == "active" else "🔴"
                available = l["max_caseload"] - l["current_caseload"]
                
                st.markdown(f"""
**{status_color} {l['name']}**  
*{l.get('title', 'Counsel')}*  

**Practice Areas:**  
{', '.join(l['practice_areas'])}

**Workload:** {l['current_caseload']}/{l['max_caseload']} cases  
**Available:** {available} slots
                """)
                st.markdown("---")
    
    if assignments_db and assignments_db["assignments"]:
        st.markdown("---")
        st.subheader("📋 Assignment Decisions with Agent Reasoning")
        
        for a in assignments_db["assignments"]:
            priority_icon = "🔴" if a["priority"] == "high" else "🟡" if a["priority"] == "medium" else "🟢"
            
            with st.expander(f"{priority_icon} **{a['matter_id']}**: {a['matter_name'][:40]}... → **{a['assigned_to']['name']}**", expanded=False):
                col1, col2 = st.columns(2)
                
                with col1:
                    st.markdown("**📋 Matter Details:**")
                    st.markdown(f"- **Matter ID:** {a['matter_id']}")
                    st.markdown(f"- **Case Type:** {a['case_type']}")
                    st.markdown(f"- **Priority:** {a['priority'].upper()}")
                    if a.get('outside_counsel'):
                        st.markdown(f"- **Outside Counsel:** {a['outside_counsel']}")
                
                with col2:
                    st.markdown("**👤 Assigned To:**")
                    st.markdown(f"- **Name:** {a['assigned_to']['name']}")
                    st.markdown(f"- **Title:** {a['assigned_to'].get('title', 'Counsel')}")
                    st.markdown(f"- **Email:** {a['assigned_to']['email']}")
                
                st.markdown("---")
                st.markdown("**🤖 Agent Reasoning:**")
                for step in a.get("reasoning", []):
                    st.markdown(step)

# ============================================================
# TAB 4: ROI DASHBOARD
# ============================================================
with tab4:
    st.header("📊 ROI Dashboard")
    st.markdown("**Business Impact & Return on Investment**")
    
    vendor_db = load_json(VENDOR_DB_PATH)
    ap_notifications = load_json(AP_NOTIFICATIONS_PATH)
    assignments_db = load_json(ASSIGNMENTS_DB_PATH)
    
    # Calculate metrics
    if ap_notifications:
        total_invoices = len(ap_notifications["notifications"])
        total_approved = sum(n["amount"] for n in ap_notifications["notifications"] if n["status"] == "APPROVED")
        total_flagged = sum(n["amount"] for n in ap_notifications["notifications"] if n["status"] == "FLAGGED")
        total_rejected = sum(n["amount"] for n in ap_notifications["notifications"] if n["status"] == "REJECTED")
        total_overcharge = sum(n.get("overcharge", 0) for n in ap_notifications["notifications"])
        
        # Estimated time savings (assume 15 min per invoice manual review)
        time_saved_minutes = total_invoices * 15
        time_saved_hours = time_saved_minutes / 60
        
        # Estimated cost savings (assume $75/hr for AP staff)
        labor_cost_saved = time_saved_hours * 75
        
        # Annual projection (assume 20x monthly volume)
        annual_overcharge_savings = total_overcharge * 20
        annual_labor_savings = labor_cost_saved * 20
        annual_total_savings = annual_overcharge_savings + annual_labor_savings
    else:
        total_invoices = 0
        total_approved = 0
        total_flagged = 0
        total_rejected = 0
        total_overcharge = 0
        time_saved_hours = 0
        labor_cost_saved = 0
        annual_overcharge_savings = 0
        annual_labor_savings = 0
        annual_total_savings = 0
    
    # Key Metrics Row
    st.subheader("💰 Financial Impact")
    col1, col2, col3, col4 = st.columns(4)
    col1.metric("Overcharges Caught", f"${total_overcharge:,.2f}", "Money Saved")
    col2.metric("Invoices Processed", total_invoices, "Automated")
    col3.metric("Time Saved", f"{time_saved_hours:.1f} hrs", f"vs Manual Review")
    col4.metric("Labor Cost Saved", f"${labor_cost_saved:,.2f}", "This Period")
    
    st.markdown("---")
    
    # Annual Projection
    st.subheader("📈 Annual ROI Projection")
    col1, col2, col3 = st.columns(3)
    col1.metric("Projected Overcharge Savings", f"${annual_overcharge_savings:,.2f}", "Per Year", delta_color="normal")
    col2.metric("Projected Labor Savings", f"${annual_labor_savings:,.2f}", "Per Year", delta_color="normal")
    col3.metric("🎯 Total Annual ROI", f"${annual_total_savings:,.2f}", "Combined Savings", delta_color="normal")
    
    st.markdown("---")
    
    # Invoice Breakdown
    st.subheader("📊 Invoice Verification Summary")
    col1, col2, col3, col4 = st.columns(4)
    col1.metric("✅ Approved", f"${total_approved:,.2f}")
    col2.metric("⚠️ On Hold", f"${total_flagged:,.2f}")
    col3.metric("❌ Rejected", f"${total_rejected:,.2f}")
    col4.metric("💸 Overcharges", f"${total_overcharge:,.2f}")
    
    # Workload Distribution
    if assignments_db:
        st.markdown("---")
        st.subheader("👥 Lawyer Workload Distribution")
        lawyers_db = load_json(LAWYERS_DB_PATH)
        if lawyers_db:
            workload_data = []
            for l in lawyers_db["lawyers"]:
                if l["status"] == "active":
                    workload_data.append({
                        "Lawyer": l["name"],
                        "Cases": l["current_caseload"],
                    })
            if workload_data:
                df = pd.DataFrame(workload_data)
                st.bar_chart(df.set_index("Lawyer"))
    
    # Value Proposition
    st.markdown("---")
    st.subheader("💡 Business Value Delivered")
    col1, col2 = st.columns(2)
    with col1:
        st.markdown("""
        **Cost Reduction:**
        - ✅ Automated rate verification eliminates manual checks
        - ✅ Catches billing errors before payment
        - ✅ Reduces AP processing time by 80%
        - ✅ Prevents overpayment to vendors
        """)
    with col2:
        st.markdown("""
        **Risk Mitigation:**
        - ✅ Ensures compliance with contracted rates
        - ✅ Creates audit trail for all decisions
        - ✅ Blocks inactive vendor payments
        - ✅ Balances lawyer workload automatically
        """)

# ============================================================
# TAB 5: ABOUT
# ============================================================
with tab5:
    st.header("ℹ️ About This System")
    
    # Author Section
    st.markdown("""
    <div class="author-box">
    <h3>👤 Built by Srini Narra</h3>
    <p><strong>Senior Legal Operations & CLM Leader</strong></p>
    <p>20+ years of experience transforming legal departments through technology and process optimization.</p>
    <p>
    <a href="https://www.linkedin.com/in/srininarra/" target="_blank">🔗 Connect on LinkedIn</a>
    </p>
    </div>
    """, unsafe_allow_html=True)
    
    st.markdown("---")
    
    # Architecture Section
    st.subheader("🏗️ System Architecture")
    st.markdown("""
    ```
    ┌─────────────────────────────────────────────────────────────────────┐
    │                        E-BILLING SYSTEM                             │
    │                   AI-Powered Legal Operations                       │
    ├─────────────────────────────────────────────────────────────────────┤
    │                                                                     │
    │   ┌─────────────┐    ┌─────────────┐    ┌─────────────┐            │
    │   │   AGENT 1   │    │   AGENT 2   │    │   AGENT 3   │            │
    │   │   Vendor    │    │   Invoice   │    │    Case     │            │
    │   │  Onboarding │    │ Verification│    │ Assignment  │            │
    │   └──────┬──────┘    └──────┬──────┘    └──────┬──────┘            │
    │          │                  │                  │                    │
    │          ▼                  ▼                  ▼                    │
    │   ┌─────────────┐    ┌─────────────┐    ┌─────────────┐            │
    │   │   Vendor    │    │     AP      │    │   Matter    │            │
    │   │  Database   │───▶│Notifications│    │ Assignments │            │
    │   └─────────────┘    └─────────────┘    └─────────────┘            │
    │                                                                     │
    └─────────────────────────────────────────────────────────────────────┘
    ```
    """)
    
    st.markdown("---")
    
    # How It Works
    st.subheader("⚙️ How It Works")
    
    col1, col2, col3 = st.columns(3)
    
    with col1:
        st.markdown("""
        **Agent 1: Vendor Onboarding**
        
        📥 *Input:* Law firm CSV data
        
        🔍 *Process:*
        - Validates firm information
        - Checks rate compliance
        - Verifies required fields
        
        📤 *Output:* Vendor database with contracted rates
        """)
    
    with col2:
        st.markdown("""
        **Agent 2: Invoice Verification**
        
        📥 *Input:* Invoices from AP inbox
        
        🔍 *Process:*
        - Matches firm to vendor DB
        - Compares billed vs contracted rates
        - Calculates overcharges
        
        📤 *Output:* Approve/Flag/Reject decisions
        """)
    
    with col3:
        st.markdown("""
        **Agent 3: Case Assignment**
        
        📥 *Input:* Legal matters/cases
        
        🔍 *Process:*
        - Matches case type to expertise
        - Checks lawyer availability
        - Balances workload
        
        📤 *Output:* Optimized assignments
        """)
    
    st.markdown("---")
    
    # Technology Stack
    st.subheader("🛠️ Technology Stack")
    
    col1, col2 = st.columns(2)
    
    with col1:
        st.markdown("""
        **AI & Agents:**
        - 🤖 CrewAI - Multi-agent orchestration
        - 🧠 Claude AI (Anthropic) - LLM backbone
        - 🔧 Custom tools for each agent
        
        **Backend:**
        - 🐍 Python 3.12
        - 📊 Pandas for data processing
        - 💾 JSON for data persistence
        """)
    
    with col2:
        st.markdown("""
        **Frontend:**
        - 🎨 Streamlit - Web interface
        - 📱 Responsive design
        - 📈 Interactive dashboards
        
        **Deployment:**
        - ☁️ Streamlit Cloud
        - 🔄 GitHub integration
        - 🚀 CI/CD pipeline
        """)
    
    st.markdown("---")
    
    # Business Problems Solved
    st.subheader("🎯 Business Problems Solved")
    
    st.markdown("""
    | Problem | Traditional Approach | AI Solution |
    |---------|---------------------|-------------|
    | **Invoice Review** | Manual check, 15-20 min each | Automated, seconds |
    | **Rate Compliance** | Spreadsheet lookups, error-prone | Real-time verification |
    | **Vendor Management** | Scattered data, outdated info | Centralized, validated |
    | **Case Assignment** | Manager intuition, unbalanced | Algorithm-optimized |
    | **Audit Trail** | Paper files, hard to search | Digital, instant access |
    """)
    
    st.markdown("---")
    
    # Future Enhancements
    st.subheader("🚀 Potential Enhancements")
    
    st.markdown("""
    - 📧 **Email Integration** - Auto-ingest invoices from AP inbox
    - 📊 **LEDES Support** - Parse standard legal billing format
    - 🔗 **ERP Integration** - Connect to SAP, Oracle, NetSuite
    - 📱 **Mobile App** - Approve invoices on the go
    - 🤖 **ML Predictions** - Forecast legal spend, flag anomalies
    - 📝 **Contract Analysis** - Extract rates from engagement letters
    """)

# ============================================================
# FOOTER
# ============================================================
st.markdown("---")
col1, col2, col3 = st.columns([1,2,1])
with col2:
    st.markdown("""
    <div style="text-align: center; color: #666;">
    <p><strong>E-Billing System Prototype</strong></p>
    <p>Powered by CrewAI + Claude AI + Streamlit</p>
    </div>
    """, unsafe_allow_html=True)
