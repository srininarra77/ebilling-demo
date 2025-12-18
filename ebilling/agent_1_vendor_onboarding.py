# ============================================================
# E-BILLING SYSTEM - AGENT 1: Vendor Onboarding
# ============================================================
#
# PURPOSE:
# Read law firm vendor data from CSV and onboard them into
# our e-billing system. Validates data and creates a 
# structured vendor database.
#
# RUN: python3 agent_1_vendor_onboarding.py
# ============================================================

from crewai import Agent, Task, Crew
from crewai.tools import tool
from langchain_anthropic import ChatAnthropic
import json
import csv
import os

llm = ChatAnthropic(model="claude-sonnet-4-20250514")


# ============================================================
# TOOL 1: Read Law Firms from CSV
# ============================================================
# This tool reads the CSV file and returns the data as JSON.
# The agent will use this to "see" the vendor data.

@tool
def read_vendor_csv(file_path: str) -> str:
    """
    Read law firm vendor data from a CSV file.
    Use this to load vendor information for onboarding.
    
    Args:
        file_path: Path to the CSV file containing vendor data
    
    Returns:
        JSON string with list of vendors and their details
    """
    try:
        vendors = []
        with open(file_path, 'r', encoding='utf-8') as f:
            reader = csv.DictReader(f)
            for row in reader:
                vendors.append(row)
        
        return json.dumps({
            "vendor_count": len(vendors),
            "vendors": vendors
        }, indent=2)
    
    except FileNotFoundError:
        return json.dumps({"error": f"File not found: {file_path}"})
    except Exception as e:
        return json.dumps({"error": str(e)})


# ============================================================
# TOOL 2: Save Vendor to Database
# ============================================================
# This tool saves validated vendors to our "database" (JSON file).
# In production, this would write to a real database.

# Our simple "database" - a JSON file
VENDOR_DB_PATH = "vendor_database.json"

@tool
def save_vendor_to_database(vendor_json: str) -> str:
    """
    Save a validated vendor to the e-billing database.
    Use this after validating vendor data to persist it.
    
    Args:
        vendor_json: JSON string with vendor details including:
                    firm_name, partner_rate, associate_rate, 
                    paralegal_rate, status, payment_terms
    
    Returns:
        Confirmation message with vendor ID
    """
    try:
        vendor = json.loads(vendor_json)
        
        # Load existing database or create new
        if os.path.exists(VENDOR_DB_PATH):
            with open(VENDOR_DB_PATH, 'r') as f:
                db = json.load(f)
        else:
            db = {"vendors": [], "next_id": 1001}
        
        # Assign vendor ID
        vendor["vendor_id"] = f"VND-{db['next_id']}"
        db["next_id"] += 1
        
        # Add to database
        db["vendors"].append(vendor)
        
        # Save database
        with open(VENDOR_DB_PATH, 'w') as f:
            json.dump(db, f, indent=2)
        
        return json.dumps({
            "status": "success",
            "message": f"Vendor '{vendor['firm_name']}' saved successfully",
            "vendor_id": vendor["vendor_id"]
        })
    
    except json.JSONDecodeError:
        return json.dumps({"status": "error", "message": "Invalid JSON format"})
    except Exception as e:
        return json.dumps({"status": "error", "message": str(e)})


# ============================================================
# TOOL 3: Validate Vendor Data
# ============================================================
# Checks if vendor data meets our requirements.

@tool
def validate_vendor(vendor_json: str) -> str:
    """
    Validate vendor data against e-billing requirements.
    Use this before saving a vendor to ensure data quality.
    
    Args:
        vendor_json: JSON string with vendor details
    
    Returns:
        Validation result with any errors found
    """
    try:
        vendor = json.loads(vendor_json)
        errors = []
        warnings = []
        
        # Required fields
        required = ["firm_name", "partner_rate", "associate_rate", "status", "payment_terms"]
        for field in required:
            if field not in vendor or not vendor[field]:
                errors.append(f"Missing required field: {field}")
        
        # Rate validations
        try:
            partner_rate = float(vendor.get("partner_rate", 0))
            if partner_rate > 800:
                warnings.append(f"Partner rate ${partner_rate}/hr exceeds preferred cap of $800/hr")
            if partner_rate < 200:
                errors.append(f"Partner rate ${partner_rate}/hr seems too low - please verify")
        except ValueError:
            errors.append("Partner rate must be a number")
        
        try:
            associate_rate = float(vendor.get("associate_rate", 0))
            if associate_rate > 500:
                warnings.append(f"Associate rate ${associate_rate}/hr exceeds preferred cap of $500/hr")
        except ValueError:
            errors.append("Associate rate must be a number")
        
        # Status validation
        if vendor.get("status") not in ["active", "inactive"]:
            errors.append("Status must be 'active' or 'inactive'")
        
        # Payment terms validation
        valid_terms = ["net_30", "net_45", "net_60"]
        if vendor.get("payment_terms") not in valid_terms:
            errors.append(f"Payment terms must be one of: {valid_terms}")
        
        # Return result
        is_valid = len(errors) == 0
        return json.dumps({
            "is_valid": is_valid,
            "firm_name": vendor.get("firm_name", "Unknown"),
            "errors": errors,
            "warnings": warnings
        }, indent=2)
    
    except json.JSONDecodeError:
        return json.dumps({"is_valid": False, "errors": ["Invalid JSON format"]})


# ============================================================
# AGENT: Vendor Onboarding Specialist
# ============================================================

vendor_onboarding_agent = Agent(
    role="Vendor Onboarding Specialist",
    
    goal="Read law firm data from CSV, validate each vendor, and onboard valid vendors into the e-billing system",
    
    backstory="""You are a legal operations specialist responsible for 
    managing the law firm vendor database. You carefully validate each 
    vendor's information before adding them to the system. You check 
    billing rates against company guidelines and ensure all required 
    information is present. You flag any concerns but still process 
    vendors that meet minimum requirements.""",
    
    tools=[read_vendor_csv, validate_vendor, save_vendor_to_database],
    
    llm=llm,
    verbose=True
)


# ============================================================
# TASK: Onboard Vendors from CSV
# ============================================================

onboarding_task = Task(
    description="""
    Onboard law firm vendors from the CSV file: law_firms.csv
    
    Steps:
    1. Use read_vendor_csv tool to load the vendor data
    2. For EACH vendor:
       a. Use validate_vendor tool to check their data
       b. If valid (even with warnings), use save_vendor_to_database
       c. If invalid, note the errors but don't save
    3. Provide a summary report showing:
       - Total vendors processed
       - Successfully onboarded (with vendor IDs)
       - Failed validation (with reasons)
       - Any warnings to review
    """,
    
    expected_output="""A summary report with:
    - Count of vendors processed
    - List of successfully onboarded vendors with their IDs
    - List of any vendors that failed validation
    - Any warnings for management review""",
    
    agent=vendor_onboarding_agent
)


# ============================================================
# CREW
# ============================================================

crew = Crew(
    agents=[vendor_onboarding_agent],
    tasks=[onboarding_task],
    verbose=True
)


# ============================================================
# RUN
# ============================================================

if __name__ == "__main__":
    print("="*60)
    print("E-BILLING SYSTEM - Agent 1: Vendor Onboarding")
    print("="*60)
    print("\nThis agent will:")
    print("1. Read law firms from CSV")
    print("2. Validate each vendor")
    print("3. Save valid vendors to database")
    print("4. Generate summary report")
    print("="*60 + "\n")
    
    # Clean up any existing database for fresh demo
    if os.path.exists(VENDOR_DB_PATH):
        os.remove(VENDOR_DB_PATH)
        print("(Cleared existing database for fresh demo)\n")
    
    result = crew.kickoff()
    
    print("\n" + "="*60)
    print("ONBOARDING COMPLETE")
    print("="*60)
    print(result)
    
    # Show the database
    print("\n" + "="*60)
    print("VENDOR DATABASE CONTENTS:")
    print("="*60)
    if os.path.exists(VENDOR_DB_PATH):
        with open(VENDOR_DB_PATH, 'r') as f:
            db = json.load(f)
            print(f"Total vendors in database: {len(db['vendors'])}")
            for v in db['vendors']:
                print(f"  - {v['vendor_id']}: {v['firm_name']} ({v['status']})")


# ============================================================
# KEY CONCEPTS IN THIS LESSON:
# ============================================================
#
# 1. MULTIPLE TOOLS: Agent has 3 tools it can call:
#    - read_vendor_csv: Load data from file
#    - validate_vendor: Check data quality
#    - save_vendor_to_database: Persist to storage
#
# 2. TOOL CHAINING: Agent decides the order:
#    read → validate → save (for each vendor)
#
# 3. DATA PERSISTENCE: Simple JSON "database"
#    (In production, use real database)
#
# 4. VALIDATION LOGIC: Business rules in tools
#    - Rate caps
#    - Required fields
#    - Valid status values
#
# NEXT: Agent 2 - Invoice Processing
# ============================================================
