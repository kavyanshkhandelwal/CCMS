# Campus Complaint Management System (CCMS)

A web platform where students and staff can lodge, track and resolve campus complaints, and the administration gets visibility and accountability over the whole process.

Built by **Group 17 (GNR)**, IIIT Vadodara, for the Software Project Management course.

## Features

- Role-based login: Student, Staff, Department and Admin
- Structured complaints: 8 categories, description and optional photo (up to 2 MB)
- Automatic routing of each complaint to the right department
- Status tracking: Pending, In-Progress, Resolved, Rejected, Closed
- 48-hour SLA with automatic escalation: Department Staff, Department Head, Administration
- Feedback and closure: the complainant confirms the fix or re-opens the complaint
- Admin reports: category trends, department performance, recurring problems

## Tech Stack

Python, Flask, Jinja2 templates, Flask-SQLAlchemy, SQLite (development) / PostgreSQL (production), Gunicorn

## Installation and Run

```bash
git clone https://github.com/kavyanshkhandelwal/CCMS.git
cd CCMS
pip install -r requirements.txt
python app.py
```

Then open **http://127.0.0.1:5000** in your browser. The database tables and default accounts are created automatically on first run.

## Default Accounts (for demo only)

| Role | Email | Password |
|---|---|---|
| Admin | admin@campus.edu | admin123 |
| Department (e.g. Hostel Office) | dept1@campus.edu | dept123 |

Students and staff can register from the sign-up page. Change the default passwords before any real deployment.

## Configuration (optional environment variables)

| Variable | Purpose | Default |
|---|---|---|
| `SECRET_KEY` | Session security key | development key |
| `DATABASE_URL` | PostgreSQL connection string | SQLite file |
| `SLA_HOURS` | Hours before a complaint escalates | 48 |

## Team

| Name | ID |
|---|---|
| Kavyansh Khandelwal | 202351063 |
| Naman Singh | 202351087 |
| Charitra Jain | 202351021 |
| Ronak Vaghela | 202351152 |

### Instructor: Dr. Karan Verma
