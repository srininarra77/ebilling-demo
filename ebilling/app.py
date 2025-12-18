"""
E-Billing System - Web Demo
"""

import streamlit as st
import pandas as pd
import json
import os
import csv
from datetime import datetime
from pathlib import Path

SCRIPT_DIR = Path(__file__).parent.resolve()

st.set_page_config(page_title="E-Billing System", page_icon="⚖️", layout="wide")

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
            results["rejected"].append({"invoice_id": invoice["invoice_id"], "firm_name": firm_name, "reason": "Vendor not in database"})
            continue
        if vendor.get("status") == "inactive":
            results["rejected"].append({"invoice_id": invoice["invoice_id"], "firm_name": firm_name, "reason": "Vendor is INACTIVE"})
            continue
        discrepancies = []
        total_overcharge = 0
        contracted_rates = {"partner": float(vendor.get("partner_rate", 0)), "associate": float(vendor.get("associate_rate", 0)), "paralegal": float(vendor.get("paralegal_rate", 0))}
        for item in invoice.get("line_items", []):
            level = item.get("level", "").lower()
            billed_rate = float(item.get("rate", 0))
            contracted_rate = contracted_rates.get(level, 0)
            if billed_rate > contracted_rate:
                overcharge = (billed_rate - contracted_rate) * item.get("hours", 0)
                total_overcharge += overcharge
                discrepancies.append({"timekeeper": item.get("timekeeper"), "level": level, "billed": billed_rate, "contracted": contracted_rate, "overcharge": overcharge})
        notification = {"notification_id": f"AP-{len(notifications['notifications']) + 1:04d}", "invoice_id": invoice["invoice_id"], "firm_name": firm_name, "amount": invoice.get("total_amount"), "timestamp": datetime.now().isoformat()}
        if discrepancies:
            notification["status"] = "FLAGGED"
            notification["action"] = "HOLD_PAYMENT"
            notification["overcharge"] = total_overcharge
            notification["discrepancies"] = discrepancies
            results["flagged"].append({"invoice_id": invoice["invoice_id"], "firm_name": firm_name, "amount": invoice.get("total_amount"), "overcharge": total_overcharge, "discrepancies": discrepancies})
        else:
            notification["status"] = "APPROVED"
            notification["action"] = "RELEASE_PAYMENT"
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
    area_mapping = {"litigation": ["litigation"], "patent_infringement": ["patent_infringement", "ip_trademark"], "ip_trademark": ["ip_trademark", "patent_infringement"], "m&a": ["m&a"], "employment": ["employment"], "regulatory": ["regulatory"], "contract_review": ["contract_review"], "real_estate": ["real_estate"]}
    for matter in matters:
        case_type = matter.get("case_type", "").lower()
        search_areas = area_mapping.get(case_type, [case_type])
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
            assignment = {"assignment_id": f"ASN-{len(assignments['assignments']) + 1:04d}", "matter_id": matter["matter_id"], "matter_name": matter["matter_name"], "case_type": case_type, "priority": matter.get("priority"), "assigned_to": {"lawyer_id": best_lawyer["lawyer_id"], "name": best_lawyer["name"], "email": best_lawyer["email"]}, "outside_counsel": matter.get("outside_counsel", "")}
            assignments["assignments"].append(assignment)
            for l in lawyers_db["lawyers"]:
                if l["lawyer_id"] == best_lawyer["lawyer_id"]:
                    l["current_caseload"] += 1
                    break
            results["assigned"].append({"matter_id": matter["matter_id"], "matter_name": matter["matter_name"], "case_type": case_type, "assigned_to": best_lawyer["name"]})
        else:
            results["unassigned"].append({"matter_id": matter["matter_id"], "matter_name": matter["matter_name"], "case_type": case_type, "reason": "No available lawyer"})
    save_json(ASSIGNMENTS_DB_PATH, assignments)
    save_json(LAWYERS_DB_PATH, lawyers_db)
    return results

st.title("⚖️ E-Billing System Demo")
st.markdown("**3 AI Agents for Legal Operations**")

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

tab1, tab2, tab3, tab4 = st.tabs(["📋 Agent 1: Vendors", "💰 Agent 2: Invoices", "⚖️ Agent 3: Cases", "📊 Dashboard"])

with tab1:
    st.header("Agent 1: Vendor Onboarding")
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
                st.markdown(f"{'🟢' if v['status'] == 'active' else '🔴'} **{v['vendor_id']}**: {v['firm_name']}")

with tab2:
    st.header("Agent 2: Invoice Verification")
    col1, col2 = st.columns(2)
    with col1:
        st.subheader("📥 Invoices")
        invoices = load_json(INBOX_PATH)
        if invoices:
            for inv in invoices:
                with st.expander(f"📄 {inv['invoice_id']} - {inv['firm_name']}"):
                    st.markdown(f"**Total:** ${inv['total_amount']:,.2f}")
    with col2:
        st.subheader("🤖 Run Agent")
        vendor_db = load_json(VENDOR_DB_PATH)
        if not vendor_db:
            st.warning("⚠️ Run Agent 1 first")
        else:
            if st.button("▶️ Run Invoice Verification", type="primary", key="run_agent2"):
                with st.spinner("Verifying..."):
                    results = run_invoice_verification()
                st.success(f"✅ Approved: {len(results['approved'])}")
                if results["flagged"]:
                    st.warning(f"⚠️ Flagged: {len(results['flagged'])}")
                if results["rejected"]:
                    st.error(f"❌ Rejected: {len(results['rejected'])}")
        ap_notifications = load_json(AP_NOTIFICATIONS_PATH)
        if ap_notifications:
            st.subheader("📬 AP Notifications")
            for n in ap_notifications["notifications"]:
                if n["status"] == "APPROVED":
                    st.success(f"✅ {n['invoice_id']}: ${n['amount']:,.2f} - RELEASE")
                else:
                    st.warning(f"⚠️ {n['invoice_id']}: ${n['amount']:,.2f} - HOLD")

with tab3:
    st.header("Agent 3: Case Assignment")
    col1, col2 = st.columns(2)
    with col1:
        st.subheader("📁 Matters")
        df = pd.read_csv(MATTERS_CSV)
        st.dataframe(df[["matter_id", "matter_name", "case_type", "priority"]], use_container_width=True)
    with col2:
        st.subheader("🤖 Run Agent")
        if st.button("▶️ Run Case Assignment", type="primary", key="run_agent3"):
            with st.spinner("Assigning..."):
                results = run_case_assignment()
            st.success(f"✅ Assigned: {len(results['assigned'])}")
        assignments_db = load_json(ASSIGNMENTS_DB_PATH)
        if assignments_db:
            st.subheader("📋 Assignments")
            for a in assignments_db["assignments"]:
                st.markdown(f"**{a['matter_id']}**: {a['matter_name']} → {a['assigned_to']['name']}")

with tab4:
    st.header("📊 Dashboard")
    col1, col2, col3 = st.columns(3)
    vendor_db = load_json(VENDOR_DB_PATH)
    ap_notifications = load_json(AP_NOTIFICATIONS_PATH)
    assignments_db = load_json(ASSIGNMENTS_DB_PATH)
    col1.metric("Vendors", len(vendor_db["vendors"]) if vendor_db else 0)
    col2.metric("Invoices", len(ap_notifications["notifications"]) if ap_notifications else 0)
    col3.metric("Assignments", len(assignments_db["assignments"]) if assignments_db else 0)

st.markdown("---")
st.markdown("*E-Billing Demo | CrewAI + Streamlit*")
