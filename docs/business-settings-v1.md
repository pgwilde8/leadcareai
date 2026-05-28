# Business settings (Phase 1O)

Business users can view and edit profile and lead-handling settings for their linked business.

## Routes

| Method | Path | Description |
|--------|------|-------------|
| GET | `/business/settings` | Settings form (`?saved=1` shows success) |
| POST | `/business/settings` | Save settings |

Access: `business_user` with a `business_users` link only. Partners and admins are redirected to `/login`.

## Editable fields

| Field | Model column | Notes |
|-------|----------------|-------|
| Business name | `name` | Required |
| Industry | `industry` | Optional |
| Website | `website_url` | Optional |
| Contact email | `contact_email` | Optional |
| Contact phone | `main_phone` | Optional |
| SMS display name | `sms_signature` | Used in default missed-call text |
| Custom missed-call SMS | `missed_call_textback_message` | Optional; blank = platform default |
| Lead intake notes | `lead_intake_prompt` | Saved only; AI unchanged in 1O |
| Notification email | `notification_email` | Saved; not sent yet |
| Notification phone | `notification_phone` | Saved; not sent yet |

## Read-only Twilio numbers

Assigned numbers are listed from `phone_numbers` (number, provider, status). Business users cannot add, edit, or remove numbers.

## Custom missed-call message

**Default** (when column is null/empty):

`{business.name or sms_signature}: Sorry we missed your call. What can we help you with today? Reply STOP to opt out.`

**Rules when saving custom text:**

- Whitespace-only input is rejected
- Empty field clears custom message (reverts to default)
- Max 240 characters after normalization
- Must not contain `http://`, `https://`, or `www.`
- If `STOP` is missing, ` Reply STOP to opt out.` is appended automatically
- Custom text cannot remove compliance language

**Runtime:** `send_missed_call_textback()` uses `build_missed_call_textback_body(business)` which prefers `missed_call_textback_message`, then default.

## Notifications

See [business-notifications-v1.md](business-notifications-v1.md).

- **notification_email** — email alerts for missed-call leads and inbound SMS replies
- **notification_phone** — staff SMS alerts (not customer text-backs)

Alerts are best-effort. SMTP and Twilio must be configured for delivery.

## Admin visibility

`/admin/businesses/{id}` shows contact/notification fields, missed-call message, and existing phone number table.

## Limitations

- One business per user (first `business_users` link)
- No Stripe, Twilio provisioning, A2P, or onboarding wizard
- `lead_intake_prompt` is not passed to OpenAI yet
- No link URLs in missed-call SMS (V1)

## URL

`https://leadcareai.com/business/settings`
