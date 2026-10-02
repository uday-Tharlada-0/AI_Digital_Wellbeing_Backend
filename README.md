# AI Digital Wellbeing Backend

Flask backend for an AI-powered Digital Wellbeing application.

The backend provides REST APIs for authentication, Android screen-time
tracking, application usage, usage sessions, session classification,
analytics, productivity scoring, suggestions, and productivity prediction.

The project is designed to work with a native Android application built
with Kotlin and a Base44-based mobile UI.

---

## 1. Project Overview

The Digital Wellbeing system collects real screen-time data directly from
an Android device using Android's `UsageStatsManager`.

The Android application is responsible for:

- User login and registration
- Requesting Android Usage Access permission
- Reading real application usage
- Detecting application usage sessions
- Uploading usage data to the Flask backend

The Flask backend is responsible for:

- Authentication
- User management
- Storing usage data
- Storing application information
- Storing usage sessions
- Session classification
- Productivity calculations
- Analytics
- Personalized suggestions
- Productivity prediction
- Serving REST APIs to the mobile UI

Base44 is used as the mobile application's UI layer and communicates with
the Flask backend through REST APIs.

---

## 2. System Architecture

```text
                         ┌─────────────────────┐
                         │    Android Device   │
                         │                     │
                         │ Kotlin Application  │
                         │                     │
                         │ UsageStatsManager   │
                         └──────────┬──────────┘
                                    │
                                    │ REST API
                                    ▼
                         ┌─────────────────────┐
                         │    Flask Backend    │
                         │                     │
                         │ Authentication      │
                         │ Usage APIs          │
                         │ Session APIs        │
                         │ Analytics           │
                         │ Suggestions         │
                         │ Prediction           │
                         └──────────┬──────────┘
                                    │
                                    ▼
                         ┌─────────────────────┐
                         │    PostgreSQL       │
                         │     Database        │
                         └──────────┬──────────┘
                                    ▲
                                    │
                                    │ REST API
                         ┌──────────┴──────────┐
                         │       Base44        │
                         │    Mobile UI        │
                         │                     │
                         │ Home                │
                         │ Usage               │
                         │ Sessions            │
                         │ Suggestions         │
                         │ Prediction          │
                         └─────────────────────┘
3. Main Features
Authentication

The backend supports mobile authentication using token-based
authentication.

Supported operations:

User login
User registration
Token generation
Token validation
User information retrieval

Mobile authentication endpoints are separated from the traditional
web-session authentication flow.

Android Usage Tracking

The Android application uses:

Android UsageStatsManager

to collect real device usage.

The application can collect:

Total screen time
Application usage
Application package names
Application names
Usage duration
Individual usage sessions
Session start time
Session end time

The backend stores the uploaded information in PostgreSQL in production.

Usage Sessions

In addition to aggregated application usage, the system stores individual
usage sessions.

Example:

YouTube
10:15 AM → 10:28 AM
13 minutes

Chrome
10:35 AM → 10:47 AM
12 minutes

Sessions can be classified by the user.

A session can contain:

Category
Productive / non-productive status
Classification status

This allows the same application to have different purposes in different
sessions.

For example:

YouTube
    ├── Educational session → Productive
    └── Entertainment session → Non-productive

The system therefore does not permanently assume that an application is
always productive or always non-productive.

4. Productivity Score

The backend calculates a productivity score from usage data.

The basic calculation is:

Productivity Score =
(Productive Minutes / Total Screen Time Minutes) × 100

Example:

Total Screen Time = 120 minutes
Productive Time   = 60 minutes

Productivity Score =
60 / 120 × 100

= 50

The score is represented on a 0–100 scale.

When classified session data is available, productive time is calculated
from classified sessions.

Aggregated Android usage remains the source of truth for total screen time.

5. Usage History and Personalization

The application changes its interpretation of usage depending on how much
history is available.

Day 1
  ↓
Basic observations

Days 2–6
  ↓
Early usage history

7+ days
  ↓
Personalized trends and comparisons

The goal is to avoid making unsupported judgments about a user's behavior
when there is not enough historical information.

6. AI Productivity Prediction

The backend contains a machine-learning prediction pipeline using
scikit-learn.

The prediction system can forecast future usage and productivity metrics.

The prediction response can contain:

{
    "today": {
        "total_minutes": 320,
        "productivity_score": 62
    },
    "tomorrow": {
        "date": "2026-10-03",
        "predicted_total_minutes": 340,
        "predicted_productive_minutes": 210,
        "predicted_productivity_score": 62
    }
}

The prediction system uses historical usage information to generate
future estimates.

7. Machine Learning Pipeline

The ML pipeline is located in:

ml/
├── data_generator.py
├── feature_engineering.py
├── train_model.py
└── predictor.py
Data Sources

The prediction pipeline can work with real usage history.

When insufficient real history is available, the project can use synthetic
data for model training and development.

This makes it possible to test the prediction pipeline before a user has
accumulated a large amount of real usage history.

Features

The prediction pipeline uses historical usage information including:

Day of week
Weekend indicator
Historical total usage
Historical productive usage
Productivity score
Recent usage averages
Lagged usage values
Rolling averages
Model

The project uses:

RandomForestRegressor

with:

MultiOutputRegressor

for multi-output prediction.

The prediction pipeline can forecast:

Future total screen time
Future productive minutes
Future productivity score
8. Suggestions

The backend provides suggestions based on available usage information.

Suggestions can use:

Current usage
Productivity score
Recent usage history
Usage trends
Prediction results

The goal is to provide practical observations rather than hard-coded
judgments about individual applications.

9. Project Structure
AI_Digital_Wellbeing_Backend/
│
├── app.py
├── config.py
├── extensions.py
├── models.py
├── mobile_auth.py
├── app_catalog.py
├── activitywatch_service.py
├── seed_db.py
├── requirements.txt
│
├── routes/
│   ├── __init__.py
│   ├── auth.py
│   ├── dashboard.py
│   ├── applications.py
│   ├── alerts.py
│   ├── analytics.py
│   ├── focus.py
│   ├── settings.py
│   ├── predictions.py
│   ├── mobile.py
│   ├── mobile_analytics.py
│   └── mobile_suggestions.py
│
├── ml/
│   ├── __init__.py
│   ├── data_generator.py
│   ├── feature_engineering.py
│   ├── train_model.py
│   └── predictor.py
│
├── data/
│
├── models_store/
│
├── static/
│
└── templates/
10. Important Backend Modules
app.py

Main Flask application entry point.

Responsibilities include:

Creating the Flask application
Configuring the database
Registering blueprints
Registering middleware
Initializing database extensions
Running startup database migrations

The production server runs the Flask application using Gunicorn.

models.py

Contains the SQLAlchemy database models.

The backend uses models for information such as:

Users
Applications
Usage records
Usage sessions
Focus sessions
Settings
Other application data
mobile_auth.py

Contains token-based authentication for the Android mobile application.

Mobile tokens are generated after successful login or registration.

The Android application stores the token and sends it with authenticated
API requests using:

Authorization: Bearer <token>
routes/mobile.py

Contains the Android/mobile API.

Responsibilities include:

Mobile user information
Android usage upload
Application usage retrieval
Application information
Usage session upload
Usage session retrieval
Session classification
routes/mobile_analytics.py

Contains mobile analytics endpoints.

Responsibilities include:

Today's analytics
Screen-time totals
Application usage
Productive minutes
Productivity score
Productivity prediction
routes/mobile_suggestions.py

Provides suggestions for the mobile application based on available usage
and productivity information.

11. Mobile API

The Android application communicates with the production API:

https://ai-digital-wellbeing-backend.onrender.com

The API base path is:

/api
Authentication
Mobile Login
POST /api/mobile/login

Example request:

{
    "identifier": "username_or_email",
    "password": "password"
}

The identifier can be either a username or email address.

Mobile Registration
POST /api/mobile/register

Example request:

{
    "username": "example_user",
    "email": "user@example.com",
    "password": "password123"
}

Successful registration returns an authentication token.

The Android application can use this token immediately without requiring
a separate login step.

Current User
GET /api/mobile/me

Requires:

Authorization: Bearer <token>
12. Android Usage API
Upload Usage
POST /api/mobile/usage

The Android application uploads today's aggregated application usage.

The uploaded information includes:

Date
Application name
Package name
Usage duration
Get Usage
GET /api/mobile/usage

Retrieves stored mobile usage information.

Applications
GET /api/mobile/apps

Returns applications associated with the user's usage data.

Update Application
PATCH /api/mobile/apps/<id>

Used to update application information such as classification.

13. Usage Sessions API
Upload Sessions
POST /api/mobile/sessions

The Android application sends individual usage sessions.

Example:

{
    "sessions": [
        {
            "app_name": "YouTube",
            "package_name": "com.google.android.youtube",
            "start_time": "2026-10-02T05:00:00Z",
            "end_time": "2026-10-02T05:15:00Z"
        }
    ]
}

The backend converts timestamps into the appropriate local representation
for the stored session data.

Duplicate sessions are prevented so that reopening the Android application
does not repeatedly create identical session records.

Get Sessions
GET /api/mobile/sessions

Optional date:

/api/mobile/sessions?date=2026-10-02

The response includes:

Session ID
Application name
Package name
Start time
End time
Duration
Category
Productivity status
Classification status
Classify Session
PATCH /api/mobile/sessions/<id>

Example:

{
    "category": "education",
    "is_productive": true
}

This allows users to decide how a particular usage session should be
interpreted.

14. Mobile Analytics API
Today's Analytics
GET /api/mobile/analytics

Provides information used by the Base44 mobile UI, including:

Total screen time
Productive minutes
Productivity score
Application usage
Most-used application
Application count
Session information

The backend uses aggregated Android usage as the source of truth for total
screen time.

Classified session information is used when calculating productive usage.

Productivity Prediction
GET /api/mobile/analytics/prediction

Returns the current day's metrics and the predicted next day's metrics.

Example:

{
    "today": {
        "total_minutes": 320,
        "productivity_score": 62
    },
    "tomorrow": {
        "date": "2026-10-03",
        "predicted_productive_minutes": 210,
        "predicted_total_minutes": 340,
        "predicted_productivity_score": 62
    }
}
15. Mobile Suggestions API
GET /api/mobile/suggestions

Returns suggestions generated from the user's available usage and
productivity information.

16. Existing Web API

The original Flask dashboard APIs are still available.

Dashboard
GET /api/dashboard/today
Applications
GET /api/applications
POST /api/applications
PATCH /api/applications/<id>
DELETE /api/applications/<id>
Application Usage
POST /api/applications/<id>/log-usage
Alerts
GET /api/alerts
PATCH /api/alerts/global
PATCH /api/alerts/app-limit/<id>
PATCH /api/alerts/notifications
Analytics
GET /api/analytics/daily-trends?days=
GET /api/analytics/time-of-day
GET /api/analytics/week-over-week
GET /api/analytics/insights
GET /api/analytics/export
Focus
GET /api/focus/sessions?date=
POST /api/focus/sessions/start
POST /api/focus/sessions/<id>/complete
GET /api/focus/trend?days=
Settings
GET /api/settings
PATCH /api/settings
Original Prediction API
GET /api/predictions/forecast?days=
POST /api/predictions/train
GET /api/predictions/model-info
17. Database
Development

SQLite can be used during local development.

SQLite is useful for:

Local development
Testing
Initial experimentation
Running the project without an external database
Production

The deployed backend uses PostgreSQL.

Production architecture:

Flask
  ↓
SQLAlchemy
  ↓
PostgreSQL

The database URL is supplied through an environment variable rather than
being hard-coded in the source code.

18. Environment Configuration

Important environment variables include:

SECRET_KEY
DATABASE_URL

Example:

SECRET_KEY=your-secret-key
DATABASE_URL=postgresql://...

Do not commit production secrets or database credentials to GitHub.

19. Local Development Setup
Requirements

Recommended Python version:

Python 3.12

The production deployment currently uses Python 3.12.

Create Virtual Environment
Linux / macOS
python3.12 -m venv venv
source venv/bin/activate
Windows
py -3.12 -m venv venv
venv\Scripts\activate
Install Dependencies
pip install -r requirements.txt
Run the Application
python app.py

The development server will normally be available at:

http://localhost:5000
20. Production Deployment

The backend is deployed on Render.

Production service:

AI_Digital_Wellbeing_Backend

Production API:

https://ai-digital-wellbeing-backend.onrender.com

The production server runs using Gunicorn:

gunicorn app:app

The backend uses PostgreSQL in production.

21. Android Application Integration

The Android application is a native Kotlin application.

The Android layer is responsible for accessing device-specific functionality
that cannot be obtained directly from a web application.

The important Android component is:

UsageStatsManager

The application requests:

PACKAGE_USAGE_STATS

through Android's Usage Access settings.

The user must explicitly allow Usage Access before screen-time information
can be collected.

New User Flow

A new user follows this flow:

Install application
       ↓
Kotlin Login / Register
       ↓
Register account
       ↓
Token saved
       ↓
Usage Access screen
       ↓
Android Usage Access settings
       ↓
User grants permission
       ↓
Usage collection
       ↓
Upload to Flask
       ↓
PostgreSQL
       ↓
Base44 mobile UI
Existing User Flow
Open application
       ↓
Stored authentication token
       ↓
Check Usage Access
       ↓
Permission available?
       │
       ├── No
       │    ↓
       │  Usage Access screen
       │
       └── Yes
            ↓
        Collect usage
            ↓
        Upload usage
            ↓
        Base44
22. Base44 Integration

The Base44 application is used as the mobile UI layer.

Base44 does not act as the primary backend database or authentication
system.

The mobile UI communicates with the Flask backend.

The Base44 application uses the Flask mobile token:

dwb_api_token

The token is stored on the client and sent to protected Flask endpoints as:

Authorization: Bearer <token>

The Base44 application consumes APIs such as:

GET /api/mobile/analytics
GET /api/mobile/analytics/prediction
GET /api/mobile/sessions
GET /api/mobile/suggestions

Session classification is also performed through the Flask API.

23. Data Flow
Usage Upload
Android UsageStatsManager
        ↓
UsageStatsHelper
        ↓
UsageSyncManager
        ↓
ApiClient
        ↓
POST /api/mobile/usage
        ↓
Flask
        ↓
UsageRecord
        ↓
PostgreSQL
Session Upload
Android UsageStatsManager
        ↓
UsageStatsHelper
        ↓
Session detection
        ↓
UsageSyncManager
        ↓
POST /api/mobile/sessions
        ↓
Flask
        ↓
UsageSession
        ↓
PostgreSQL
Base44 Analytics
Base44
   ↓
GET /api/mobile/analytics
   ↓
Flask
   ↓
PostgreSQL
   ↓
Analytics calculation
   ↓
JSON response
   ↓
Base44 UI
24. Session Classification

Applications are not permanently assigned a productivity category.

Instead, the user can classify individual sessions.

For example:

Chrome
    10:00 → 10:30
    Education
    Productive

Chrome
    20:00 → 20:40
    Entertainment
    Non-productive

This allows the system to handle applications that can have multiple
purposes.

New applications and sessions can remain uncategorized until the user
provides a classification.

25. Duplicate Session Protection

The mobile session API checks for an existing session with the same:

User
Application
Start time
End time

before creating a new session.

This prevents repeated synchronization from creating identical sessions.

This is important because the Android application can synchronize usage
multiple times during the same day.

26. Timezone Handling

Android sends session timestamps using UTC ISO-8601 timestamps.

The backend converts them into Indian Standard Time (IST) before storing
the session timestamps used by the application.

This keeps session times consistent with the user's local usage.

27. Requirements

The main Python dependencies include:

Flask
Flask-SQLAlchemy
Flask-Cors
scikit-learn
pandas
numpy
joblib
openpyxl
python-dateutil
itsdangerous
gunicorn
psycopg2-binary
psycopg[binary]

See requirements.txt for the exact versions used by the project.

28. Development Notes

The project originally started as a Flask + SQLite screen-time dashboard.

It has since been extended to support:

Native Android usage tracking
Mobile authentication
Mobile registration
PostgreSQL production storage
Usage sessions
Session classification
Productivity scoring
Mobile analytics
Productivity prediction
Personalized suggestions
Base44 mobile UI integration
Android Usage Access permission flow
Duplicate session protection
IST timestamp handling

The original web dashboard APIs remain available alongside the mobile APIs.

29. Security Notes

Authentication tokens are required for protected mobile endpoints.

Clients should send:

Authorization: Bearer <token>

Production secrets must be stored in environment variables.

Do not commit the following to the repository:

SECRET_KEY
DATABASE_URL
Passwords
Authentication tokens
API keys
30. Current Production Stack
Component	Technology
Android application	Kotlin
Android UI	Jetpack Compose
Device usage tracking	UsageStatsManager
Mobile UI	Base44
Backend	Flask
ORM	Flask-SQLAlchemy
Database - Development	SQLite
Database - Production	PostgreSQL
Machine Learning	scikit-learn
Data Processing	Pandas / NumPy
Model Persistence	Joblib
Production Server	Gunicorn
Production Hosting	Render
31. Current Architecture Summary
                    DIGITAL WELLBEING
                           │
             ┌─────────────┴─────────────┐
             │                           │
       Android Kotlin                Base44 UI
             │                           │
             │                           │
       UsageStatsManager                 │
             │                           │
             └─────────────┬─────────────┘
                           │
                           ▼
                  Flask REST API
                           │
          ┌────────────────┼────────────────┐
          │                │                │
          ▼                ▼                ▼
    Authentication      Usage          Analytics
                         Sessions       Prediction
          │                │                │
          └────────────────┼────────────────┘
                           │
                           ▼
                      PostgreSQL
                           │
                           ▼
                   AI / Analytics
32. Current User Flow
                    ┌───────────────┐
                    │   Open App    │
                    └───────┬───────┘
                            │
                            ▼
                 ┌─────────────────────┐
                 │ Authentication Token │
                 │      available?      │
                 └─────────┬───────────┘
                           │
                 ┌─────────┴─────────┐
                 │                   │
                NO                  YES
                 │                   │
                 ▼                   ▼
          Kotlin Login/        Check Usage
          Registration             Access
                 │                   │
                 │             ┌─────┴─────┐
                 │             │           │
                 │            NO          YES
                 │             │           │
                 │             ▼           ▼
                 │       Usage Access   Collect
                 │          Screen       Usage
                 │             │           │
                 │             ▼           │
                 │       Android Settings │
                 │             │           │
                 └──────► Token + ◄───────┘
                         Permission
                              │
                              ▼
                       Upload to Flask
                              │
                              ▼
                         PostgreSQL
                              │
                              ▼
                         Base44 UI
33. Future Improvements

Possible future extensions include:

Automatic background usage synchronization
More advanced session classification
Improved productivity prediction
Personalized behavioral trends
More detailed analytics
Notification and reminder system
Focus-mode integration
Improved recommendation models
More advanced machine-learning models
Production database optimization
Automated model retraining
Better mobile offline synchronization
```
