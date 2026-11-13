# CAPACITY CONNECT — API Documentation

Base URL: `http://localhost:5000`

All responses are JSON. All protected routes require:
```
Authorization: Bearer <jwt>
```

Standard error shape: `{"error": "..."}` with an appropriate HTTP status
(400 validation, 401 auth, 403 authorization, 404 not found, 409 conflict).

---

## Auth — `/api/auth`

| Method | Path | Role | Description |
|---|---|---|---|
| POST | `/register-organization` | public | `{organization_name, admin_name, admin_email, admin_password, registration_number}` → creates org (PENDING) + ADMIN user |
| POST | `/verify-organization/<org_id>` | public* | MOCK/DEMO verification → `MOCK_VERIFIED` or `REJECTED` |
| POST | `/activate-organization/<org_id>` | public* | Activates an org once `MOCK_VERIFIED` |
| POST | `/login` | public | `{email, password, organization_code?}` → `{token, user}` |
| POST | `/logout` | any | Audit-logs logout (JWTs are stateless; client discards token) |
| GET | `/me` | any | Current user |
| POST | `/activate-invite` | public | `{email, organization_code, new_password}` — invited users set their password |

\* In production these admin-ish endpoints should themselves be placed behind
an ADMIN-authenticated flow or a signed one-time link; left open here to keep
the hackathon demo flow simple end-to-end.

---

## Admin — `/api/admin` (ADMIN unless noted)

| Method | Path | Role | Description |
|---|---|---|---|
| GET | `/departments` | ADMIN, MANAGER | List org's departments |
| POST | `/departments` | ADMIN | Create department |
| PUT | `/departments/<id>` | ADMIN | Update department |
| DELETE | `/departments/<id>` | ADMIN | Delete department |
| GET | `/managers` | ADMIN | List managers |
| POST | `/managers` | ADMIN | Invite a manager |
| GET | `/trainers` | ADMIN, MANAGER | List trainer profiles |
| POST | `/trainers` | ADMIN | Invite + create a trainer profile |
| POST | `/trainers/<id>/suspend` | ADMIN | Suspend trainer organization-wide |
| POST | `/employees` | ADMIN, MANAGER | Invite an employee (manager invites auto-assign to that manager) |

---

## Manager — `/api/manager` (MANAGER only)

| Method | Path | Description |
|---|---|---|
| GET | `/employees` | List **your** employees only |
| PUT | `/employees/<id>` | Edit permitted fields (job_title, skills, department_id) — 403 if not your employee |
| GET | `/employees/<id>/progress` | Enrollment/progress for your employee |
| GET | `/employees/<id>/assessment-results` | Assessment results for your employee |
| GET | `/employees/<id>/skill-gaps` | Skill gaps for your employee |
| GET | `/employees/<id>/certificates` | Certificates for your employee |
| POST | `/training-requirements` | Create a training requirement |
| GET | `/training-requirements/<id>/matches` | Recompute + return ranked trainer matches |
| POST | `/training-requirements/<id>/assign` | Assign trainer+course to your employee(s) → creates Enrollments |
| POST | `/enrollments/<id>/remove-trainer` | Remove trainer from an assignment you created |
| GET | `/trainer-quality-alerts` | Alerts touching your employees' training |

---

## Trainer — `/api/trainer` (TRAINER only)

| Method | Path | Description |
|---|---|---|
| GET/PUT | `/profile` | View/update own trainer profile |
| POST | `/profile/domains` | Add a domain/skill |
| POST | `/profile/certifications` | Add a certification |
| POST | `/profile/experience` | Add experience entry |
| POST | `/profile/intro-video` | Upload intro video (multipart `file`) — metadata only stored on the profile |
| POST | `/courses` | Create a course |
| GET | `/courses` | List your courses |
| POST | `/assessments` | Create an assessment (with questions/options) for your own course |
| GET | `/assigned-training` | Enrollments where you are the trainer |
| GET | `/feedback` | Feedback + quality metrics about you |

---

## Employee — `/api/employee` (EMPLOYEE only)

| Method | Path | Description |
|---|---|---|
| GET | `/profile` | Your employee profile |
| GET | `/enrollments` | Your training enrollments |
| GET | `/certificates` | Your certificates |
| GET | `/skill-gaps` | Your skill-gap records |
| POST | `/feedback` | Submit feedback for one of your own enrollments |

---

## Courses — `/api/courses` (any authenticated role)

| Method | Path | Description |
|---|---|---|
| GET | `` | List org's active courses |
| GET | `/<id>` | Course detail |

---

## Training lifecycle — `/api/training`

| Method | Path | Role | Description |
|---|---|---|---|
| PUT | `/enrollments/<id>/progress` | EMPLOYEE | Update own progress %; auto-transitions ASSIGNED→IN_PROGRESS→COMPLETED, or DEADLINE_EXPIRED if past end_date |
| POST | `/deadline-sweep` | ADMIN | Batch-expire overdue enrollments in the org (intended for a scheduled job) |
| POST | `/enrollments/<id>/extend` | MANAGER | Explicit, single extension of a DEADLINE_EXPIRED enrollment you assigned |

---

## Assessments — `/api/assessments`

| Method | Path | Role | Description |
|---|---|---|---|
| GET | `/<id>` | EMPLOYEE | View assessment (questions/options, **no** correct-answer flags) |
| POST | `/<id>/submit` | EMPLOYEE | Submit answers → auto-scored, pass/fail; blocked (403) until training completion % is met; blocked once max_attempts reached |
| POST | `/results/<id>/proctoring-events` | EMPLOYEE | Submit a DEMO/simulated proctoring event (`FACE_MISSING`, `MULTIPLE_FACES`, `CAMERA_INTERRUPTION`, `SUSPICIOUS_BEHAVIOR`) |
| GET | `/results/<id>/proctoring-summary` | MANAGER, ADMIN, TRAINER | `CLEAR` or `REVIEW_REQUIRED` overall status + events |
| POST | `/results/<id>/proctoring-review` | MANAGER | Record a human review decision/notes on a specific event |

---

## Feedback — `/api/feedback`

| Method | Path | Role | Description |
|---|---|---|---|
| GET | `/trainers/<trainer_id>` | ADMIN, MANAGER | Feedback for a trainer (managers see only feedback from their own employees) |

---

## Competency / Skill gaps — `/api/competency`

| Method | Path | Role | Description |
|---|---|---|---|
| POST | `/employees/<id>/recompute` | MANAGER (own employee), ADMIN (any) | Recomputes CompetencyRecord rows from skills + assessment history |

---

## Certificates — `/api/certificates`

| Method | Path | Role | Description |
|---|---|---|---|
| POST | `/issue` | MANAGER (own employee), TRAINER (own assignment), ADMIN | Issue a certificate for a COMPLETED enrollment |

---

## Notifications — `/api/notifications`

| Method | Path | Role | Description |
|---|---|---|---|
| GET | `` | any | Your own notifications (`?unread_only=true` to filter) |
| POST | `/<id>/read` | any | Mark your own notification read |
| POST | `/announcements` | ADMIN | Broadcast an announcement (optionally scoped to a role) |
| GET | `/announcements` | any | Announcements visible to your role |

---

## CAPACITY AI — `/api/ai`

| Method | Path | Role | Description |
|---|---|---|---|
| POST | `/ask` | MANAGER, ADMIN | `{"question": "..."}` → `{intent, verified_data, answer}`. Manager queries are scoped to their own team only. |

Example supported questions: *"Who failed Advanced Python?"*, *"Which
employees need retraining?"*, *"What's our team's average score?"*, *"Which
department has the highest pass rate?"* (ADMIN only), *"Which manager has the
best performance?"* (ADMIN only).

---

## Health

`GET /api/health` → `{"status": "ok", "service": "capacity-connect-backend"}`
