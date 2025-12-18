"""
E-Billing System - Web Demo
===========================
A Streamlit app to demo the 3 CrewAI agents.

Run locally: streamlit run app.py
"""

import streamlit as st
import pandas as pd
import json
import os
import csv
from datetime import datetime

# Page config
st.set_page_config(
    page_title="E-Billing System",
    page_icon="⚖️",
    layout="wide"
)

# ============================================================
# SHARED PATHS
# ============================================================
VENDOR_DB_PATH = "vendor_database.json"
LAWYERS_DB_PATH = "internal_lawyers.json"
ASSIGNMENTS_DB_PATH = "matter_assignments.json"
AP_NOTIFICATIONS_PATH = "ap_notifications.json"
INBOX_PATH = "inbox/invoices.json"

# ============================================================
# HELPER FUNCTIONS
# ============================================================

def load_json(path):
    """Load JSON file if exists"""
    if os.path.exists(path):
        with open(path, 'r') as f:
            return json.load(f)
    return None

def save_json(path, data):
    """Save data to JSON file"""
    with open(path, 'w') as f:
        json.dump(data, f, indent=2)

def reset_demo_data():
    """Reset all generated data for fresh demo"""
    for path in [VENDOR_DB_PATH, ASSIGNMENTS_DB_PATH, AP_NOTIFICATIONS_PATH]:
        if os.path.exists(path):
            os.remove(path)
    
    # Reset lawyer caseloads
    if os.path.exists(LAWYERS_DB_PATH):
        with open(LAWYERS_DB_PATH, 'r') as f:
            lawyers = json.load(f)
        for l in lawyers["lawyers"]:
            l["current_caseload"] = 0
        save_json(LAWYERS_DB_PATH, lawyers)
    
    st.success("✅ Demo data reset!")

# ============================================================
# AGENT 1: Vendor Onboarding (Simplified for demo)
# ============================================================

def run_vendor_onboarding():
    """Simplified vendor onboarding without CrewAI (for demo)"""
    
    # Read CSV
    vendors = []
    with open("law_firms.csv", 'r') as f:
        reader = csv.DictReader(f)
        for row in reader:
            vendors.append(row)
    
    # Process vendors
    db = {"vendors": [], "next_id": 1001}
    results = {"onboarded": [], "warnings": []}
    
    for vendor in vendors:
        # Validate
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
            results["onboarded"].append({
                "vendor_id": vendor["vendor_id"],
                "firm_name": vendor["firm_name"],
                "status": vendor["status"],
                "warnings": warnings
            })
            if warnings:
                results["warnings"].extend(warnings)
    
    # Save database
    save_json(VENDOR_DB_PATH, db)
    
    return results

# ============================================================
# AGENT 2: Invoice Verification (Simplified for demo)
# ============================================================

def run_invoice_verification():
    """Simplified invoice verification without CrewAI"""
    
    # Load invoices
    with open(INBOX_PATH, 'r') as f:
        invoices = json.load(f)
    
    # Load vendor database
    vendor_db = load_json(VENDOR_DB_PATH)
    if not vendor_db:
        return {"error": "Run Agent 1 first to create vendor database"}
    
    results = {"approved": [], "flagged": [], "rejected": []}
    notifications = {"notifications": []}
    
    for invoice in invoices:
        firm_name = invoice.get("firm_name", "")
        
        # Find vendor
        vendor = None
        for v in vendor_db["vendors"]:
            if firm_name.lower() in v["firm_name"].lower():
                vendor = v
                break
        
        if not vendor:
            results["rejected"].append({
                "invoice_id": invoice["invoice_id"],
                "firm_name": firm_name,
                "reason": "Vendor not in database"
            })
            continue
        
        if vendor.get("status") == "inactive":
            results["rejected"].append({
                "invoice_id": invoice["invoice_id"],
                "firm_name": firm_name,
                "reason": "Vendor is INACTIVE"
            })
            continue
        
        # Check rates
        discrepancies = []
        total_overcharge = 0
        
        contracted_rates = {
            "partner": float(vendor.get("partner_rate", 0)),
            "associate": float(vendor.get("associate_rate", 0)),
            "paralegal": float(vendor.get("paralegal_rate", 0))
        }
        
        for item in invoice.get("line_items", []):
            level = item.get("level", "").lower()
            billed_rate = float(item.get("rate", 0))
            contracted_rate = contracted_rates.get(level, 0)
            
            if billed_rate > contracted_rate:
                overcharge = (billed_rate - contracted_rate) * item.get("hours", 0)
                total_overcharge += overcharge
                discrepancies.append({
                    "timekeeper": item.get("timekeeper"),
                    "level": level,
                    "billed": billed_rate,
                    "contracted": contracted_rate,
                    "overcharge": overcharge
                })
        
        # Create notification
        notification = {
            "notification_id": f"AP-{len(notifications['notifications']) + 1:04d}",
            "invoice_id": invoice["invoice_id"],
            "firm_name": firm_name,
            "amount": invoice.get("total_amount"),
            "timestamp": datetime.now().isoformat()
        }
        
        if discrepancies:
            notification["status"] = "FLAGGED"
            notification["action"] = "HOLD_PAYMENT"
            notification["overcharge"] = total_overcharge
            notification["discrepancies"] = discrepancies
            results["flagged"].append({
                "invoice_id": invoice["invoice_id"],
                "firm_name": firm_name,
                "amount": invoice.get("total_amount"),
                "overcharge": total_overcharge,
                "discrepancies": discrepancies
            })
        else:
            notification["status"] = "APPROVED"
            notification["action"] = "RELEASE_PAYMENT"
            results["approved"].append({
                "invoice_id": invoice["invoice_id"],
                "firm_name": firm_name,
                "amount": invoice.get("total_amount")
            })
        
        notifications["notifications"].append(notification)
    
    # Save notifications
    save_json(AP_NOTIFICATIONS_PATH, notifications)
    
    return results

# ============================================================
# AGENT 3: Case Assignment (Simplified for demo)
# ============================================================

def run_case_assignment():
    """Simplified case assignment without CrewAI"""
    
    # Load matters
    matters = []
    with open("matters.csv", 'r') as f:
        reader = csv.DictReader(f)
        for row in reader:
            matters.append(row)
    
    # Load lawyers
    with open(LAWYERS_DB_PATH, 'r') as f:
        lawyers_db = json.load(f)
    
    # Reset caseloads for demo
    for l in lawyers_db["lawyers"]:
        l["current_caseload"] = 0
    
    results = {"assigned": [], "unassigned": []}
    assignments = {"assignments": []}
    
    # Practice area mapping
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
        search_areas = area_mapping.get(case_type, [case_type])
        
        # Find available lawyer
        best_lawyer = None
        for lawyer in lawyers_db["lawyers"]:
            if lawyer["status"] != "active":
                continue
            
            available = lawyer["max_caseload"] - lawyer["current_caseload"]
            if available <= 0:
                continue
            
            for area in search_areas:
                if area in [pa.lower() for pa in lawyer["practice_areas"]]:
                    if best_lawyer is None or available > (best_lawyer["max_caseload"] - best_lawyer["current_caseload"]):
                        best_lawyer = lawyer
                    break
        
        if best_lawyer:
            # Create assignment
            assignment = {
                "assignment_id": f"ASN-{len(assignments['assignments']) + 1:04d}",
                "matter_id": matter["matter_id"],
                "matter_name": matter["matter_name"],
                "case_type": case_type,
                "priority": matter.get("priority"),
                "assigned_to": {
                    "lawyer_id": best_lawyer["lawyer_id"],
                    "name": best_lawyer["name"],
                    "email": best_lawyer["email"]
                },
                "outside_counsel": matter.get("outside_counsel", "")
            }
            assignments["assignments"].append(assignment)
            
            # Update caseload
            for l in lawyers_db["lawyers"]:
                if l["lawyer_id"] == best_lawyer["lawyer_id"]:
                    l["current_caseload"] += 1
                    break
            
            results["assigned"].append({
                "matter_id": matter["matter_id"],
                "matter_name": matter["matter_name"],
                "case_type": case_type,
                "assigned_to": best_lawyer["name"]
            })
        else:
            results["unassigned"].append({
                "matter_id": matter["matter_id"],
                "matter_name": matter["matter_name"],
                "case_type": case_type,
                "reason": "No available lawyer with matching expertise"
            })
    
    # Save results
    save_json(ASSIGNMENTS_DB_PATH, assignments)
    save_json(LAWYERS_DB_PATH, lawyers_db)
    
    return results

# ============================================================
# STREAMLIT UI
# ============================================================

st.title("⚖️ E-Billing System Demo")
st.markdown("**3 AI Agents for Legal Operations**")

# Sidebar
with st.sidebar:
    st.header("🔧 Controls")
    if st.button("🔄 Reset Demo Data", type="secondary"):
        reset_demo_data()
    
    st.markdown("---")
    st.markdown("### Agent Status")
    
    vendor_db = load_json(VENDOR_DB_PATH)
    assignments_db = load_json(ASSIGNMENTS_DB_PATH)
    ap_notifications = load_json(AP_NOTIFICATIONS_PATH)
    
    st.markdown(f"**Vendors:** {'✅ ' + str(len(vendor_db['vendors'])) if vendor_db else '❌ Not run'}")
    st.markdown(f"**Invoices:** {'✅ ' + str(len(ap_notifications['notifications'])) if ap_notifications else '❌ Not run'}")
    st.markdown(f"**Assignments:** {'✅ ' + str(len(assignments_db['assignments'])) if assignments_db else '❌ Not run'}")

# Main tabs
tab1, tab2, tab3, tab4 = st.tabs(["📋 Agent 1: Vendors", "💰 Agent 2: Invoices", "⚖️ Agent 3: Cases", "📊 Dashboard"])

# ============================================================
# TAB 1: Vendor Onboarding
# ============================================================
with tab1:
    st.header("Agent 1: Vendor Onboarding")
    st.markdown("Reads law firms from CSV, validates data, and onboards to database.")
    
    col1, col2 = st.columns(2)
    
    with col1:
        st.subheader("📁 Input: law_firms.csv")
        df = pd.read_csv("law_firms.csv")
        st.dataframe(df, use_container_width=True)
    
    with col2:
        st.subheader("🤖 Run Agent")
        if st.button("▶️ Run Vendor Onboarding", type="primary", key="run_agent1"):
            with st.spinner("Processing vendors..."):
                results = run_vendor_onboarding()
            
            st.success(f"✅ Onboarded {len(results['onboarded'])} vendors")
            
            if results.get("warnings"):
                st.warning(f"⚠️ Warnings: {len(results['warnings'])}")
                for w in results["warnings"]:
                    st.markdown(f"- {w}")
        
        # Show current database
        vendor_db = load_json(VENDOR_DB_PATH)
        if vendor_db:
            st.subheader("📦 Vendor Database")
            for v in vendor_db["vendors"]:
                status_icon = "🟢" if v["status"] == "active" else "🔴"
                st.markdown(f"{status_icon} **{v['vendor_id']}**: {v['firm_name']}")
                st.markdown(f"   Partner: ${v['partner_rate']}/hr | {v['payment_terms']}")

# ============================================================
# TAB 2: Invoice Verification
# ============================================================
with tab2:
    st.header("Agent 2: Invoice Verification")
    st.markdown("Verifies invoice rates against contracted vendor rates.")
    
    col1, col2 = st.columns(2)
    
    with col1:
        st.subheader("📥 Input: Invoices in AP Inbox")
        invoices = load_json(INBOX_PATH)
        if invoices:
            for inv in invoices:
                with st.expander(f"📄 {inv['invoice_id']} - {inv['firm_name']}"):
                    st.markdown(f"**Matter:** {inv['matter']}")
                    st.markdown(f"**Total:** ${inv['total_amount']:,.2f}")
                    st.markdown("**Line Items:**")
                    for item in inv["line_items"]:
                        st.markdown(f"- {item['timekeeper']} ({item['level']}): {item['hours']}hrs @ ${item['rate']}/hr = ${item['amount']:,.2f}")
    
    with col2:
        st.subheader("🤖 Run Agent")
        
        vendor_db = load_json(VENDOR_DB_PATH)
        if not vendor_db:
            st.warning("⚠️ Run Agent 1 first to create vendor database")
        else:
            if st.button("▶️ Run Invoice Verification", type="primary", key="run_agent2"):
                with st.spinner("Verifying invoices..."):
                    results = run_invoice_verification()
                
                st.success(f"✅ Approved: {len(results['approved'])}")
                if results["flagged"]:
                    st.warning(f"⚠️ Flagged: {len(results['flagged'])}")
                if results["rejected"]:
                    st.error(f"❌ Rejected: {len(results['rejected'])}")
        
        # Show notifications
        ap_notifications = load_json(AP_NOTIFICATIONS_PATH)
        if ap_notifications:
            st.subheader("📬 AP Notifications")
            for n in ap_notifications["notifications"]:
                if n["status"] == "APPROVED":
                    st.success(f"✅ {n['invoice_id']}: {n['firm_name']} - ${n['amount']:,.2f} - RELEASE PAYMENT")
                elif n["status"] == "FLAGGED":
                    st.warning(f"⚠️ {n['invoice_id']}: {n['firm_name']} - ${n['amount']:,.2f} - HOLD (${n.get('overcharge', 0):,.2f} overcharge)")
                else:
                    st.error(f"❌ {n['invoice_id']}: {n['firm_name']} - REJECTED")

# ============================================================
# TAB 3: Case Assignment
# ============================================================
with tab3:
    st.header("Agent 3: Case/Matter Assignment")
    st.markdown("Auto-assigns matters to internal lawyers based on practice area and workload.")
    
    col1, col2 = st.columns(2)
    
    with col1:
        st.subheader("📁 Input: matters.csv")
        df = pd.read_csv("matters.csv")
        st.dataframe(df[["matter_id", "matter_name", "case_type", "priority"]], use_container_width=True)
        
        st.subheader("👥 Internal Lawyers")
        lawyers_db = load_json(LAWYERS_DB_PATH)
        if lawyers_db:
            for l in lawyers_db["lawyers"]:
                status_icon = "🟢" if l["status"] == "active" else "🔴"
                capacity = f"{l['current_caseload']}/{l['max_caseload']}"
                st.markdown(f"{status_icon} **{l['name']}** ({capacity})")
                st.markdown(f"   {', '.join(l['practice_areas'])}")
    
    with col2:
        st.subheader("🤖 Run Agent")
        if st.button("▶️ Run Case Assignment", type="primary", key="run_agent3"):
            with st.spinner("Assigning matters..."):
                results = run_case_assignment()
            
            st.success(f"✅ Assigned: {len(results['assigned'])} matters")
            if results["unassigned"]:
                st.warning(f"⚠️ Unassigned: {len(results['unassigned'])}")
        
        # Show assignments
        assignments_db = load_json(ASSIGNMENTS_DB_PATH)
        if assignments_db:
            st.subheader("📋 Assignments")
            
            # Group by lawyer
            by_lawyer = {}
            for a in assignments_db["assignments"]:
                name = a["assigned_to"]["name"]
                if name not in by_lawyer:
                    by_lawyer[name] = []
                by_lawyer[name].append(a)
            
            for lawyer, matters in by_lawyer.items():
                with st.expander(f"👤 {lawyer} ({len(matters)} matters)"):
                    for m in matters:
                        priority_icon = "🔴" if m["priority"] == "high" else "🟡" if m["priority"] == "medium" else "🟢"
                        st.markdown(f"{priority_icon} **{m['matter_id']}**: {m['matter_name']}")
                        st.markdown(f"   Type: {m['case_type']}")

# ============================================================
# TAB 4: Dashboard
# ============================================================
with tab4:
    st.header("📊 Dashboard")
    
    col1, col2, col3 = st.columns(3)
    
    vendor_db = load_json(VENDOR_DB_PATH)
    ap_notifications = load_json(AP_NOTIFICATIONS_PATH)
    assignments_db = load_json(ASSIGNMENTS_DB_PATH)
    
    with col1:
        st.metric("Total Vendors", len(vendor_db["vendors"]) if vendor_db else 0)
        if vendor_db:
            active = sum(1 for v in vendor_db["vendors"] if v["status"] == "active")
            st.caption(f"{active} active, {len(vendor_db['vendors']) - active} inactive")
    
    with col2:
        if ap_notifications:
            approved = sum(1 for n in ap_notifications["notifications"] if n["status"] == "APPROVED")
            flagged = sum(1 for n in ap_notifications["notifications"] if n["status"] == "FLAGGED")
            st.metric("Invoices Processed", len(ap_notifications["notifications"]))
            st.caption(f"✅ {approved} approved, ⚠️ {flagged} flagged")
        else:
            st.metric("Invoices Processed", 0)
    
    with col3:
        st.metric("Matters Assigned", len(assignments_db["assignments"]) if assignments_db else 0)
        if assignments_db:
            lawyers_db = load_json(LAWYERS_DB_PATH)
            active_lawyers = sum(1 for l in lawyers_db["lawyers"] if l["current_caseload"] > 0)
            st.caption(f"Across {active_lawyers} lawyers")
    
    # Financial summary
    if ap_notifications:
        st.subheader("💰 Financial Summary")
        
        total_approved = sum(n["amount"] for n in ap_notifications["notifications"] if n["status"] == "APPROVED")
        total_flagged = sum(n["amount"] for n in ap_notifications["notifications"] if n["status"] == "FLAGGED")
        total_overcharge = sum(n.get("overcharge", 0) for n in ap_notifications["notifications"])
        
        col1, col2, col3 = st.columns(3)
        col1.metric("Approved for Payment", f"${total_approved:,.2f}")
        col2.metric("On Hold", f"${total_flagged:,.2f}")
        col3.metric("Overcharges Detected", f"${total_overcharge:,.2f}")
    
    # Workload distribution
    if assignments_db:
        st.subheader("👥 Lawyer Workload")
        lawyers_db = load_json(LAWYERS_DB_PATH)
        
        workload_data = []
        for l in lawyers_db["lawyers"]:
            if l["status"] == "active":
                workload_data.append({
                    "Lawyer": l["name"],
                    "Current": l["current_caseload"],
                    "Max": l["max_caseload"],
                    "Available": l["max_caseload"] - l["current_caseload"]
                })
        
        df = pd.DataFrame(workload_data)
        st.bar_chart(df.set_index("Lawyer")["Current"])

# Footer
st.markdown("---")
st.markdown("*E-Billing System Demo | Built with CrewAI + Streamlit*")
