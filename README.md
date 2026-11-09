# 💳 Expense Splitter V1 — Backend REST API

A highly secure, robust expense-sharing REST API built with **Python**, **Django REST Framework (DRF)**, and **PostgreSQL** [cite: 1]. It features absolute monetary precision via integer paise math and guarantees transactional consistency using group-level database row locks [cite: 1].

---

## 🏗️ Architecture & Core Safeties

The backend strictly enforces the architectural boundaries defined in the **Shared Contract V1 (Revision 1.2)** [cite: 1]:

### 1. 💎 Integer Paise Math (No Floats)
* All incoming monetary values are validated as text decimal strings (e.g., `"120.50"`) [cite: 1].
* Internally, values are transformed and stored as integer paise (e.g., `₹120.50` becomes `12050 paise`) [cite: 1].
* **Leftover Paise Distribution:** When dividing an expense equally causes a division remainder, the remainder is distributed sequentially (+1 paise each) to participants ordered by their ascending UUID strings, making split operations 100% deterministic [cite: 1].

### 2. 🔒 Transaction Serialization & Row Locking
* To eliminate deadlocks and race conditions, all state-changing endpoints enforce a **group-first lock order** [cite: 1].
* Mutations acquire a row lock on the parent `Group` first (`select_for_update()`), followed by subordinate entity records in stable UUID order [cite: 1].
* This serializes concurrent writes, preventing issues like duplicate settlement generation or inconsistent member removals [cite: 1].

### 3. 🛡️ Lifecycle Preservation (Revision 1.2 Engine)
* **Soft-Deleted Expenses:** `DELETE /api/v1/expenses/{id}/` soft-deletes the expense, hiding it from listings and balances, but fully preserves its shares and comments for auditing [cite: 1].
* **Soft-Removed Memberships:** Members cannot be physically purged. They are flagged as `removed` with a `removed_at` timestamp only if they have no active financial references [cite: 1].
* **100-Member Cap:** Active memberships are strictly capped at 100 users per group to enforce system stability [cite: 1].

---

## ✨ Features Walkthrough

| Module | Purpose | Scope / Permissions |
| :--- | :--- | :--- |
| **Accounts** | Registration, single-use expiring token email verification, session authentication, and profile management [cite: 1]. | Public (Registration/Login) / Signed-in (Profile/Photo Upload) [cite: 1]. |
| **Groups & Invites** | Create shared pools, look up active/verified users, and process group access [cite: 1]. | Admin invites, removes, and edits [cite: 1]; Invitee accepts or declines [cite: 1]. |
| **Expenses & Shares** | Add description, amount, date, payer, and select custom participant subsets [cite: 1]. | Group members view [cite: 1]; Creator or Admin edits/deletes before freezing [cite: 1]. |
| **Live Balances** | Check real-time aggregate net balances of unassigned expenses [cite: 1]. | Group members; blocks settlement if active blockers exist [cite: 1]. |
| **Settlements** | Freeze all eligible unassigned expenses and compute a greedy matching plan [cite: 1]. | Admin-only trigger; creates immutable frozen snapshot [cite: 1]. |
| **Payment Flow** | Payer reports payment; receiver marks as confirmed (verified outside the app) [cite: 1]. | Multi-step handshake; unlocks url-encoded `upi://pay` URI for participants [cite: 1]. |
| **Notifications** | Contextual alerts for invitations, expenses, and payment actions [cite: 1]. | Recipient-only visibility with global unread counter [cite: 1]. |

---

## 🛠️ How to Use & API Interaction Examples

### 1. Initialize CSRF Protection
Before sending any state-mutating requests, fetch the CSRF token:
* **Endpoint:** `GET /api/v1/auth/csrf/` [cite: 1]
* **Success Response (200):** Sets the `csrftoken` cookie [cite: 1].
```json
{ "message": "CSRF cookie set" }
```

### 2. Live Balance Preview
Retrieve the status of unassigned financial obligations before freezing them:
* **Endpoint:** `GET /api/v1/groups/{group_id}/balances/` [cite: 1]
* **Success Response (200):** [cite: 1]
```json
{
  "group_id": "8a3e4567-e89b-42d3-a456-426614174000",
  "currency": "INR",
  "unsettled_expense_total": "1200.00",
  "members": [
    {
      "user": { "id": "123e4567-e89b-42d3-a456-426614174001", "username": "aman" },
      "net_balance": "600.00"
    },
    {
      "user": { "id": "123e4567-e89b-42d3-a456-426614174002", "username": "rahul" },
      "net_balance": "-150.00"
    },
    {
      "user": { "id": "123e4567-e89b-42d3-a456-426614174003", "username": "priya" },
      "net_balance": "-450.00"
    }
  ],
  "can_generate_settlement": true,
  "blockers": []
}
```
*Note: If `blockers` contains strings like `PENDING_INVITATIONS` or `ACTIVE_SETTLEMENT_EXISTS`, settlement generation will be rejected with a `409 Conflict` [cite: 1].*

### 3. Generate Settlement
Freeze all unassigned expenses and calculate optimal transactions via greedy matching:
* **Endpoint:** `POST /api/v1/groups/{group_id}/settlements/` [cite: 1]
* **Success Response (201):** [cite: 1]
```json
{
  "settlement": {
    "id": "5f3e4567-e89b-42d3-a456-426614174100",
    "group_id": "8a3e4567-e89b-42d3-a456-426614174000",
    "sequence_number": 1,
    "status": "pending",
    "created_by": "123e4567-e89b-42d3-a456-426614174001",
    "expense_ids": ["e13e4567-e89b-42d3-a456-426614174999"],
    "transactions": [
      {
        "id": "t13e4567-e89b-42d3-a456-426614174888",
        "payer": { "id": "123e4567-e89b-42d3-a456-426614174002", "username": "rahul" },
        "receiver": { "id": "123e4567-e89b-42d3-a456-426614174001", "username": "aman" },
        "amount": "150.00",
        "status": "pending"
      }
    ]
  }
}
```

---

## 📁 Repository Structure
```text
expense-splitter/
  backend/
    manage.py
    requirements.txt
    .env.example
    config/            # Main project configuration (settings, routes)
    accounts/          # Users, token generator, registration/login engine
    groups/            # Groups, memberships, invitations
    expenses/          # Expenses, transactional integer shares
    settlements/       # Greedy settlement algorithm and immutable snapshotted balances
    notifications/     # Recipient-isolated global unread notification engine
    common/            # Global custom exception maps and monetary utilities
```
