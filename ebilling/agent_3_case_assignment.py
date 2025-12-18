# ============================================================
# E-BILLING SYSTEM - AGENT 3: Case/Matter Assignment
# ============================================================
#
# PURPOSE:
# Read new cases/matters from CSV, match them to internal 
# lawyers based on practice area, and auto-assign considering
# current caseload.
#
# WORKFLOW:
# 1. Read matters from CSV
# 2. Read internal lawyers and their practice areas
# 3. Match case type to lawyer expertise
# 4. Check lawyer availability (caseload)
# 5. Assign and update records
# 6. Generate assignment report
#
# RUN: python3 agent_3_case_assignment.py
# ============================================================

from crewai import Agent, Task, Crew
from crewai.tools import tool
from langchain_anthropic import ChatAnthropic
import json
import csv
import os
from datetime import datetime

llm = ChatAnthropic(model="claude-sonnet-4-20250514")


# ============================================================
# PATHS
# ============================================================

MATTERS_CSV_PATH = "matters.csv"
LAWYERS_DB_PATH = "internal_lawyers.json"
ASSIGNMENTS_DB_PATH = "matter_assignments.json"


# ============================================================
# TOOL 1: Read Matters from CSV
# ============================================================

@tool
def read_matters_csv(file_path: str) -> str:
    """
    Read cases/matters from a CSV file for assignment.
    
    Args:
        file_path: Path to the CSV file containing matter data
    
    Returns:
        JSON with list of matters and their details
    """
    try:
        matters = []
        with open(file_path, 'r', encoding='utf-8') as f:
            reader = csv.DictReader(f)
            for row in reader:
                matters.append(row)
        
        # Group by case type for summary
        case_types = {}
        for m in matters:
            ct = m.get("case_type", "other")
            case_types[ct] = case_types.get(ct, 0) + 1
        
        return json.dumps({
            "matter_count": len(matters),
            "case_type_summary": case_types,
            "matters": matters
        }, indent=2)
    
    except FileNotFoundError:
        return json.dumps({"error": f"File not found: {file_path}"})
    except Exception as e:
        return json.dumps({"error": str(e)})


# ============================================================
# TOOL 2: Get Internal Lawyers
# ============================================================

@tool
def get_internal_lawyers() -> str:
    """
    Get list of internal lawyers with their practice areas and availability.
    Use this to find lawyers who can handle specific case types.
    
    Returns:
        JSON with lawyers, their practice areas, and current caseload
    """
    try:
        if not os.path.exists(LAWYERS_DB_PATH):
            return json.dumps({"error": "Lawyers database not found"})
        
        with open(LAWYERS_DB_PATH, 'r') as f:
            data = json.load(f)
        
        # Add availability info
        for lawyer in data["lawyers"]:
            available_capacity = lawyer["max_caseload"] - lawyer["current_caseload"]
            lawyer["available_capacity"] = available_capacity
            lawyer["is_available"] = (
                lawyer["status"] == "active" and 
                available_capacity > 0
            )
        
        # Create practice area index
        practice_area_index = {}
        for lawyer in data["lawyers"]:
            if lawyer["is_available"]:
                for area in lawyer["practice_areas"]:
                    if area not in practice_area_index:
                        practice_area_index[area] = []
                    practice_area_index[area].append({
                        "lawyer_id": lawyer["lawyer_id"],
                        "name": lawyer["name"],
                        "available_capacity": lawyer["available_capacity"]
                    })
        
        return json.dumps({
            "total_lawyers": len(data["lawyers"]),
            "available_lawyers": sum(1 for l in data["lawyers"] if l["is_available"]),
            "practice_area_index": practice_area_index,
            "lawyers": data["lawyers"]
        }, indent=2)
    
    except Exception as e:
        return json.dumps({"error": str(e)})


# ============================================================
# TOOL 3: Find Best Lawyer for Case
# ============================================================

@tool
def find_best_lawyer(case_type: str, priority: str) -> str:
    """
    Find the best available lawyer for a specific case type.
    Considers practice area match, current caseload, and priority.
    
    Args:
        case_type: Type of case (litigation, m&a, patent_infringement, etc.)
        priority: Case priority (high, medium, low)
    
    Returns:
        JSON with recommended lawyer or explanation if none available
    """
    try:
        if not os.path.exists(LAWYERS_DB_PATH):
            return json.dumps({"error": "Lawyers database not found"})
        
        with open(LAWYERS_DB_PATH, 'r') as f:
            data = json.load(f)
        
        # Normalize case type
        case_type_lower = case_type.lower().strip()
        
        # Find matching lawyers
        candidates = []
        for lawyer in data["lawyers"]:
            # Skip inactive or on leave
            if lawyer["status"] != "active":
                continue
            
            # Check capacity
            available = lawyer["max_caseload"] - lawyer["current_caseload"]
            if available <= 0:
                continue
            
            # Check practice area match
            if case_type_lower in [pa.lower() for pa in lawyer["practice_areas"]]:
                candidates.append({
                    "lawyer_id": lawyer["lawyer_id"],
                    "name": lawyer["name"],
                    "title": lawyer["title"],
                    "email": lawyer["email"],
                    "available_capacity": available,
                    "current_caseload": lawyer["current_caseload"],
                    "practice_areas": lawyer["practice_areas"]
                })
        
        if not candidates:
            # No exact match - suggest general counsel review
            return json.dumps({
                "found": False,
                "case_type": case_type,
                "message": f"No available lawyer with '{case_type}' expertise. Recommend manual assignment or General Counsel review.",
                "suggestion": "Assign to General Counsel for triage"
            })
        
        # Sort by available capacity (prefer less loaded lawyers for high priority)
        if priority == "high":
            # For high priority, prefer lawyers with MORE capacity
            candidates.sort(key=lambda x: x["available_capacity"], reverse=True)
        else:
            # For normal priority, balance the load
            candidates.sort(key=lambda x: x["current_caseload"])
        
        best = candidates[0]
        
        return json.dumps({
            "found": True,
            "case_type": case_type,
            "recommended_lawyer": best,
            "other_options": candidates[1:3] if len(candidates) > 1 else []
        }, indent=2)
    
    except Exception as e:
        return json.dumps({"error": str(e), "found": False})


# ============================================================
# TOOL 4: Assign Matter to Lawyer
# ============================================================

@tool
def assign_matter_to_lawyer(matter_json: str, lawyer_id: str) -> str:
    """
    Assign a matter to an internal lawyer and update records.
    
    Args:
        matter_json: JSON string with matter details
        lawyer_id: ID of the lawyer to assign (e.g., "LAW-001")
    
    Returns:
        Confirmation of assignment with details
    """
    try:
        matter = json.loads(matter_json)
        
        # Load lawyers DB
        with open(LAWYERS_DB_PATH, 'r') as f:
            lawyers_db = json.load(f)
        
        # Find the lawyer
        lawyer = None
        lawyer_index = None
        for i, l in enumerate(lawyers_db["lawyers"]):
            if l["lawyer_id"] == lawyer_id:
                lawyer = l
                lawyer_index = i
                break
        
        if not lawyer:
            return json.dumps({
                "success": False,
                "error": f"Lawyer {lawyer_id} not found"
            })
        
        # Load or create assignments DB
        if os.path.exists(ASSIGNMENTS_DB_PATH):
            with open(ASSIGNMENTS_DB_PATH, 'r') as f:
                assignments_db = json.load(f)
        else:
            assignments_db = {"assignments": []}
        
        # Create assignment record
        assignment = {
            "assignment_id": f"ASN-{len(assignments_db['assignments']) + 1:04d}",
            "matter_id": matter.get("matter_id"),
            "matter_name": matter.get("matter_name"),
            "case_type": matter.get("case_type"),
            "priority": matter.get("priority"),
            "client": matter.get("client"),
            "assigned_to": {
                "lawyer_id": lawyer["lawyer_id"],
                "name": lawyer["name"],
                "email": lawyer["email"]
            },
            "outside_counsel": matter.get("outside_counsel", "None"),
            "assigned_date": datetime.now().isoformat(),
            "status": "active"
        }
        
        # Save assignment
        assignments_db["assignments"].append(assignment)
        with open(ASSIGNMENTS_DB_PATH, 'w') as f:
            json.dump(assignments_db, f, indent=2)
        
        # Update lawyer caseload
        lawyers_db["lawyers"][lawyer_index]["current_caseload"] += 1
        with open(LAWYERS_DB_PATH, 'w') as f:
            json.dump(lawyers_db, f, indent=2)
        
        return json.dumps({
            "success": True,
            "assignment_id": assignment["assignment_id"],
            "matter_id": matter.get("matter_id"),
            "matter_name": matter.get("matter_name"),
            "assigned_to": lawyer["name"],
            "lawyer_email": lawyer["email"],
            "message": f"Matter '{matter.get('matter_name')}' assigned to {lawyer['name']}"
        }, indent=2)
    
    except Exception as e:
        return json.dumps({"success": False, "error": str(e)})


# ============================================================
# TOOL 5: Generate Assignment Report
# ============================================================

@tool
def generate_assignment_report() -> str:
    """
    Generate a summary report of all matter assignments.
    Use this after completing assignments to create a report.
    
    Returns:
        Formatted report of assignments by lawyer
    """
    try:
        if not os.path.exists(ASSIGNMENTS_DB_PATH):
            return json.dumps({"error": "No assignments found"})
        
        with open(ASSIGNMENTS_DB_PATH, 'r') as f:
            data = json.load(f)
        
        # Group by lawyer
        by_lawyer = {}
        for a in data["assignments"]:
            lawyer_name = a["assigned_to"]["name"]
            if lawyer_name not in by_lawyer:
                by_lawyer[lawyer_name] = {
                    "email": a["assigned_to"]["email"],
                    "matters": []
                }
            by_lawyer[lawyer_name]["matters"].append({
                "matter_id": a["matter_id"],
                "matter_name": a["matter_name"],
                "case_type": a["case_type"],
                "priority": a["priority"]
            })
        
        # Count by case type
        by_type = {}
        for a in data["assignments"]:
            ct = a["case_type"]
            by_type[ct] = by_type.get(ct, 0) + 1
        
        # Count by priority
        by_priority = {}
        for a in data["assignments"]:
            p = a["priority"]
            by_priority[p] = by_priority.get(p, 0) + 1
        
        return json.dumps({
            "report_date": datetime.now().isoformat(),
            "total_assignments": len(data["assignments"]),
            "by_case_type": by_type,
            "by_priority": by_priority,
            "by_lawyer": by_lawyer
        }, indent=2)
    
    except Exception as e:
        return json.dumps({"error": str(e)})


# ============================================================
# AGENT: Matter Assignment Specialist
# ============================================================

matter_assignment_agent = Agent(
    role="Matter Assignment Specialist",
    
    goal="Read new matters, match them to internal lawyers by practice area, and create assignments considering workload balance",
    
    backstory="""You are the legal operations manager responsible for assigning 
    incoming matters to the right internal lawyers. You understand that:
    
    - Cases must be assigned to lawyers with matching expertise
    - Workload must be balanced - don't overload any single lawyer
    - High priority cases should go to lawyers with more capacity
    - If no matching lawyer is available, flag for General Counsel
    - Some matters may not have outside counsel yet - that's okay
    
    You are methodical and ensure every matter gets assigned properly.""",
    
    tools=[
        read_matters_csv,
        get_internal_lawyers,
        find_best_lawyer,
        assign_matter_to_lawyer,
        generate_assignment_report
    ],
    
    llm=llm,
    verbose=True
)


# ============================================================
# TASK: Assign All Matters
# ============================================================

assignment_task = Task(
    description="""
    Process all matters from matters.csv and assign them to internal lawyers.
    
    Steps:
    1. Use read_matters_csv to load all matters from "matters.csv"
    2. Use get_internal_lawyers to see available lawyers and their practice areas
    3. For EACH matter:
       a. Use find_best_lawyer with the case_type and priority
       b. If a lawyer is found, use assign_matter_to_lawyer
       c. If no lawyer found, note it for manual review
    4. After all assignments, use generate_assignment_report
    
    Important matching rules:
    - litigation → lawyers with "litigation" practice area
    - m&a → lawyers with "m&a" practice area  
    - patent_infringement → lawyers with "patent_infringement" or "ip_trademark"
    - employment → lawyers with "employment" practice area
    - regulatory → lawyers with "regulatory" practice area
    - contract_review → lawyers with "contract_review" practice area
    - real_estate → lawyers with "real_estate" practice area
    - ip_trademark → lawyers with "ip_trademark" or "patent_infringement"
    - other/unknown → flag for General Counsel
    
    Provide a final summary showing:
    - Total matters processed
    - Successfully assigned (with lawyer names)
    - Unassigned (needing manual review)
    - Workload distribution across lawyers
    """,
    
    expected_output="""Complete assignment report showing:
    - Each matter and its assigned lawyer
    - Matters that could not be auto-assigned
    - Final workload distribution by lawyer
    - Any concerns or recommendations""",
    
    agent=matter_assignment_agent
)


# ============================================================
# CREW
# ============================================================

crew = Crew(
    agents=[matter_assignment_agent],
    tasks=[assignment_task],
    verbose=True
)


# ============================================================
# RUN
# ============================================================

if __name__ == "__main__":
    print("="*60)
    print("E-BILLING SYSTEM - Agent 3: Case/Matter Assignment")
    print("="*60)
    
    # Check prerequisites
    if not os.path.exists(MATTERS_CSV_PATH):
        print(f"\n❌ ERROR: Matters file not found: {MATTERS_CSV_PATH}")
        exit(1)
    
    if not os.path.exists(LAWYERS_DB_PATH):
        print(f"\n❌ ERROR: Lawyers database not found: {LAWYERS_DB_PATH}")
        exit(1)
    
    print("\nThis agent will:")
    print("1. Read matters from CSV")
    print("2. Match case types to lawyer expertise")
    print("3. Assign matters considering workload")
    print("4. Generate assignment report")
    print("="*60)
    
    # Show internal lawyers
    print("\nINTERNAL LAWYERS:")
    print("-"*60)
    with open(LAWYERS_DB_PATH, 'r') as f:
        lawyers = json.load(f)
        for l in lawyers["lawyers"]:
            status = "🟢" if l["status"] == "active" else "🔴"
            capacity = f"{l['current_caseload']}/{l['max_caseload']}"
            areas = ", ".join(l["practice_areas"])
            print(f"{status} {l['name']} ({l['title']})")
            print(f"   Practice: {areas}")
            print(f"   Caseload: {capacity}")
    print("="*60 + "\n")
    
    # Clean up previous assignments for fresh demo
    if os.path.exists(ASSIGNMENTS_DB_PATH):
        os.remove(ASSIGNMENTS_DB_PATH)
    
    # Reset lawyer caseloads for demo
    with open(LAWYERS_DB_PATH, 'r') as f:
        lawyers = json.load(f)
    for l in lawyers["lawyers"]:
        l["current_caseload"] = 0  # Reset for demo
    with open(LAWYERS_DB_PATH, 'w') as f:
        json.dump(lawyers, f, indent=2)
    
    result = crew.kickoff()
    
    print("\n" + "="*60)
    print("ASSIGNMENT COMPLETE")
    print("="*60)
    print(result)
    
    # Show final assignments
    print("\n" + "="*60)
    print("FINAL ASSIGNMENTS:")
    print("="*60)
    if os.path.exists(ASSIGNMENTS_DB_PATH):
        with open(ASSIGNMENTS_DB_PATH, 'r') as f:
            assignments = json.load(f)
        
        # Group by lawyer
        by_lawyer = {}
        for a in assignments["assignments"]:
            name = a["assigned_to"]["name"]
            if name not in by_lawyer:
                by_lawyer[name] = []
            by_lawyer[name].append(a)
        
        for lawyer, matters in by_lawyer.items():
            print(f"\n📋 {lawyer} ({len(matters)} matters):")
            for m in matters:
                priority_icon = "🔴" if m["priority"] == "high" else "🟡" if m["priority"] == "medium" else "🟢"
                print(f"   {priority_icon} {m['matter_id']}: {m['matter_name'][:40]}")
                print(f"      Type: {m['case_type']} | Outside Counsel: {m['outside_counsel'] or 'None'}")


# ============================================================
# EXPECTED ASSIGNMENTS:
# ============================================================
#
# Michael Torres (litigation, patent_infringement):
#   - MTR-2025-001 Widget Patent Dispute
#   - MTR-2025-005 Vendor Contract Dispute
#   - MTR-2025-010 Product Liability Claim
#   - MTR-2025-012 Competitor Trade Secret Theft
#
# Jennifer Walsh (m&a, contract_review):
#   - MTR-2025-003 TechStart Acquisition
#   - MTR-2025-006 Software License Review
#   - MTR-2025-007 DataCorp Merger (if capacity)
#
# David Kim (employment):
#   - MTR-2025-004 Employee Discrimination Claim
#   - MTR-2025-009 Wrongful Termination Suit
#   - MTR-2025-015 Sales Rep Noncompete Dispute
#
# Sarah Patel (patent_infringement, ip_trademark):
#   - MTR-2025-008 Trademark Opposition
#   - Could also handle patent cases
#
# Robert Chen (m&a, regulatory):
#   - MTR-2025-002 Annual SEC Filing
#   - MTR-2025-013 GDPR Compliance Review
#   - MTR-2025-014 Joint Venture Agreement
#
# James Mitchell (real_estate, contract_review):
#   - MTR-2025-011 Office Lease Renewal
#
# Lisa Nakamura - ON LEAVE (should not be assigned)
# ============================================================


# ============================================================
# KEY CONCEPTS IN THIS LESSON:
# ============================================================
#
# 1. MATCHING LOGIC:
#    Case type → Practice area → Available lawyer
#
# 2. WORKLOAD BALANCING:
#    Check current_caseload vs max_caseload
#    High priority gets lawyers with more capacity
#
# 3. MULTIPLE DATA SOURCES:
#    - matters.csv (input)
#    - internal_lawyers.json (reference)
#    - matter_assignments.json (output)
#
# 4. STATE UPDATES:
#    Agent updates lawyer caseload after each assignment
#
# This completes the 3-agent e-billing system!
# ============================================================
