# E-Billing System - CrewAI Agents

A simple e-billing system using CrewAI agents to manage law firm vendors and invoices.

## Workflow

```
┌─────────────────┐     ┌─────────────────┐     ┌─────────────────┐
│    AGENT 1      │     │    AGENT 2      │     │  ACCOUNTS       │
│    Vendor       │────▶│    Invoice      │────▶│  PAYABLE        │
│    Onboarding   │     │    Verification │     │  (Payment)      │
└─────────────────┘     └─────────────────┘     └─────────────────┘
        │                       │
        ▼                       ▼
  vendor_database.json    ap_notifications.json
```

## Files

| File | Purpose |
|------|---------|
| `law_firms.csv` | Sample data - 10 fictitious law firms |
| `agent_1_vendor_onboarding.py` | Onboards vendors from CSV |
| `agent_2_invoice_verification.py` | Verifies invoices against rates |
| `inbox/invoices.json` | Sample invoices (simulated email inbox) |
| `vendor_database.json` | Created by Agent 1 |
| `ap_notifications.json` | Created by Agent 2 |

## Setup

```bash
# Create folder and copy files
mkdir -p ~/ebilling
cd ~/ebilling

# Extract zip files here

# Make sure API key is set
export ANTHROPIC_API_KEY="your-key"
```

## Run Agents (in order!)

```bash
# Step 1: Onboard vendors (creates vendor_database.json)
python3 agent_1_vendor_onboarding.py

# Step 2: Verify invoices (reads vendor DB, creates AP notifications)
python3 agent_2_invoice_verification.py
```

---

## Agent 1: Vendor Onboarding

**What it does:**
1. Reads law firm data from `law_firms.csv`
2. Validates each vendor (rates, required fields, status)
3. Saves valid vendors to `vendor_database.json`

**Tools:**
| Tool | Purpose |
|------|---------|
| `read_vendor_csv` | Load vendors from CSV |
| `validate_vendor` | Check against guidelines |
| `save_vendor_to_database` | Save to JSON database |

---

## Agent 2: Invoice Verification

**What it does:**
1. Reads invoices from `inbox/invoices.json`
2. Looks up vendor contracted rates from database
3. Compares billed rates vs contracted rates
4. Approves or flags discrepancies
5. Sends notifications to AP

**Tools:**
| Tool | Purpose |
|------|---------|
| `read_invoices_from_inbox` | Load pending invoices |
| `lookup_vendor_rates` | Get contracted rates |
| `verify_invoice` | Compare rates, find issues |
| `send_ap_notification` | Notify AP of decision |

**Issues Agent 2 will catch:**
- ⚠️ Goldman Hart: Partner billed $750, contracted $700
- ⚠️ Baker & Sterling (INV-005): Partner billed $700, contracted $650
- ❌ Fitzgerald & Moore: Vendor is INACTIVE

---

## Sample Data

### Law Firms (vendor rates)
| Firm | Partner | Associate | Status |
|------|---------|-----------|--------|
| Baker & Sterling LLP | $650/hr | $425/hr | Active |
| Goldman Hart LLP | $700/hr | $450/hr | Active |
| Fitzgerald & Moore | $525/hr | $350/hr | **Inactive** |

### Sample Invoices
| Invoice | Firm | Amount | Expected Result |
|---------|------|--------|-----------------|
| INV-2025-001 | Baker & Sterling | $8,425 | ✅ Approved |
| INV-2025-002 | Goldman Hart | $11,250 | ⚠️ Flagged (rate overcharge) |
| INV-2025-003 | Chen Associates | $16,750 | ✅ Approved |
| INV-2025-004 | Fitzgerald & Moore | $6,300 | ❌ Rejected (inactive vendor) |
| INV-2025-005 | Baker & Sterling | $7,750 | ⚠️ Flagged (rate overcharge) |

---

## Agent 3: Case/Matter Assignment

**What it does:**
1. Reads matters from `matters.csv`
2. Loads internal lawyers and their practice areas
3. Matches case type to lawyer expertise
4. Checks lawyer availability (caseload)
5. Auto-assigns matters
6. Generates assignment report

**Tools:**
| Tool | Purpose |
|------|---------|
| `read_matters_csv` | Load matters from CSV |
| `get_internal_lawyers` | Get lawyers and their practice areas |
| `find_best_lawyer` | Match case type to lawyer expertise |
| `assign_matter_to_lawyer` | Create assignment, update caseload |
| `generate_assignment_report` | Summary of all assignments |

**Internal Lawyers:**
| Lawyer | Practice Areas | Max Caseload |
|--------|---------------|--------------|
| Michael Torres | Litigation, Patent | 8 |
| Jennifer Walsh | M&A, Contract Review | 6 |
| David Kim | Employment | 8 |
| Sarah Patel | Patent, Trademark | 6 |
| Robert Chen | M&A, Regulatory | 5 |
| Amanda Foster | Litigation, Employment | 8 |
| James Mitchell | Real Estate, Contract Review | 7 |
| Lisa Nakamura | Regulatory (**ON LEAVE**) | - |

**Case Type Matching:**
| Case Type | Assigned To |
|-----------|-------------|
| litigation | Michael Torres, Amanda Foster |
| m&a | Jennifer Walsh, Robert Chen |
| patent_infringement | Michael Torres, Sarah Patel |
| employment | David Kim, Amanda Foster |
| regulatory | Robert Chen, Lisa Nakamura* |
| contract_review | Jennifer Walsh, James Mitchell |
| real_estate | James Mitchell |
| ip_trademark | Sarah Patel |

*Lisa Nakamura is on leave - will not be assigned

---

## Complete System Workflow

```
┌─────────────────┐     ┌─────────────────┐     ┌─────────────────┐
│    AGENT 1      │     │    AGENT 2      │     │    AGENT 3      │
│    Vendor       │     │    Invoice      │     │    Case         │
│    Onboarding   │     │    Verification │     │    Assignment   │
└────────┬────────┘     └────────┬────────┘     └────────┬────────┘
         │                       │                       │
         ▼                       ▼                       ▼
  vendor_database.json    ap_notifications.json   matter_assignments.json
         │                       │
         └───────────────────────┘
              Agent 2 reads
              vendor rates
```

## Run All Agents

```bash
cd ~/ebilling

# Agent 1: Onboard vendors
python3 agent_1_vendor_onboarding.py

# Agent 2: Verify invoices
python3 agent_2_invoice_verification.py

# Agent 3: Assign matters
python3 agent_3_case_assignment.py
```

## Files Created

| File | Created By | Purpose |
|------|------------|---------|
| `vendor_database.json` | Agent 1 | Vendor info and rates |
| `ap_notifications.json` | Agent 2 | Payment decisions for AP |
| `matter_assignments.json` | Agent 3 | Case assignments to lawyers |

---

## 🌐 Web App Demo

The system includes a Streamlit web app for easy demos.

### Run Locally

```bash
cd ~/ebilling

# Install Streamlit
pip install streamlit pandas --break-system-packages

# Run the app
streamlit run app.py
```

Then open http://localhost:8501 in your browser.

### Deploy to Streamlit Cloud (Free)

1. Push this folder to a GitHub repo
2. Go to [share.streamlit.io](https://share.streamlit.io)
3. Click "New app"
4. Select your repo and `app.py`
5. Click "Deploy"

Your app will be live at `https://your-app-name.streamlit.app`

### Web App Features

| Tab | Description |
|-----|-------------|
| **Agent 1: Vendors** | View CSV, run onboarding, see database |
| **Agent 2: Invoices** | View invoices, verify rates, see AP notifications |
| **Agent 3: Cases** | View matters, auto-assign to lawyers |
| **Dashboard** | Summary metrics, financials, workload chart |

![Demo Screenshot](screenshot.png)
