# Room Node Credentials, Authentication, and Heartbeat Workflow

This document describes the device authentication and status behavior implemented
by this Flask backend. It also identifies the boundary between this repository
and the LoRa equipment, because the LoRa Node and Gateway firmware/protocol are
not implemented here.

## What is implemented

The backend implements:

- Per-device random credentials provisioned by an operator through a Flask CLI
  command.
- A SHA-256 credential digest stored in `room_device.credential_hash`.
- Device-key authentication for heartbeat and occupancy-event requests using
  the `X-Device-Key` HTTP header.
- Heartbeat receipt at `POST /api/device-monitoring/heartbeat`.
- Current connectivity fields on `room_device`, and transition history in
  `device_status_log`.
- A CLI operation that marks timed-out devices offline.
- Administrator-protected status, history, and summary read endpoints.

The repository does **not** include Room Node firmware, LoRa packet handling,
Gateway firmware, a LoRa-to-HTTP bridge, or an automatic background scheduler.
The exact LoRa radio message format and how the Gateway identifies a radio
sender must be implemented/configured outside this Flask code. The backend only
receives an HTTP request containing a `device_id` and its device key.

## Credential hashing

### How a key is created

An administrator first creates a device record. The create endpoint starts the
device in `PENDING` state. An operator then provisions and activates its key:

```powershell
flask --app server rotate-device-key --device-id DEV001 --activate
```

The `--activate` flag changes a device that is not already `REGISTERED` to
`REGISTERED`. The command generates a random key using Python's
`secrets.token_urlsafe(32)`, stores its SHA-256 digest, and prints the plaintext
key once. The database column contains the 64-character hexadecimal digest,
not the plaintext key.

The digest is a one-way value, not an encrypted copy of the key. It cannot be
used in place of the original key in a request: the backend hashes the supplied
key again before comparing it. The provisioned key is generated randomly with
high entropy, rather than chosen as a human password.

The command output is the only opportunity to copy that plaintext key. Store it
in the approved device/Gateway secret store and deliver it to the component that
will make authenticated HTTPS requests. Do not put it in source control, logs,
URLs, or normal device metadata. Never send `credential_hash` as the header; it
is not the device key. The backend cannot recover a lost key; run the
provision command again to rotate it. Rotation replaces the stored digest, so
the previous key stops authenticating immediately.

### How the backend checks a key

For a request, the backend:

1. Finds the `RoomDevice` row by `device_id`.
2. Rejects the request if the device, stored digest, or supplied key is missing.
3. SHA-256 hashes the supplied plaintext key and compares the resulting hex
   digest to `credential_hash` with `hmac.compare_digest`.
4. Requires `registration_status` to be `REGISTERED`.
5. For a heartbeat, also requires the assigned room to exist and be active.

Unknown devices and incorrect/missing keys receive `401 Invalid device
credentials`. A correct key for a device that is not registered receives a
`403` response. A heartbeat from a registered device assigned to an inactive
room also receives `403`.

This device key is separate from user JWTs. The embedded-device requests do not
use a WinForms user's access or refresh token.

## Embedded device and Gateway communication

### Backend-facing request contract

The heartbeat endpoint expects an HTTP `POST` with a JSON body and the device
key header:

```http
POST /api/device-monitoring/heartbeat HTTP/1.1
Host: <backend-host>
Content-Type: application/json
X-Device-Key: <plaintext-device-key>

{"device_id":"DEV001"}
```

For example, from PowerShell/curl:

```powershell
curl.exe -X POST "https://<backend-host>/api/device-monitoring/heartbeat" `
  -H "Content-Type: application/json" `
  -H "X-Device-Key: <plaintext-device-key>" `
  -d '{"device_id":"DEV001"}'
```

A successful response is HTTP `200` and includes `device_id`,
`current_status` (`ONLINE`), and `last_communication_at` in an ISO timestamp.
Malformed JSON or a missing/invalid `device_id` receives HTTP `400`.

### How LoRa fits in

The intended system can be wired conceptually as:

```text
Room Node --LoRa radio--> LoRa Gateway --HTTP(S)--> Flask backend
```

The code in this repository implements only the final HTTP(S) contract. If the
Room Node cannot make IP requests itself, the Gateway or a trusted Gateway-side
bridge must:

1. Receive the LoRa message and determine which registered Room Node sent it.
2. Map that radio identity to the backend `device_id` and its device key.
3. Send the backend HTTP request above, forwarding the matching `device_id` and
   placing the key in `X-Device-Key`.
4. Handle the HTTP response and retry transient connection failures according
   to the Gateway's own retry policy.

Those radio identity checks, LoRa payload format, key distribution to a Gateway,
and retry rules are not implemented or verified by this backend. The backend
trusts the `device_id` and `X-Device-Key` in the HTTP request; it does not
inspect LoRa metadata or independently verify which radio transmitted a packet.
Where the Gateway handles multiple Nodes, it must keep each Node's identity and
credential association separate.

Use HTTPS between the Gateway/bridge and backend so the key is encrypted in
transit. The Flask development server in `server.py` runs on its default local
interface (`127.0.0.1`) and port (`5000`) when started directly; it is not
configured there for remote Gateway access or TLS. A deployed environment must
provide a Gateway-reachable host and HTTPS termination. `127.0.0.1` is only
appropriate when the client is on the same machine as the backend.

## Step-by-step device lifecycle

1. **Create the device.** An administrator creates a Room Device and assigns it
   to a room. The management service sets `registration_status` to `PENDING`.
2. **Activate and provision.** An operator runs `rotate-device-key` with
   `--activate`. The device becomes `REGISTERED`; the operator securely stores
   the one-time plaintext key.
3. **Configure the sender.** The Node/Gateway bridge associates the radio
   sender with the backend's `device_id` and device key. That bridge behavior
   is outside this repository.
4. **Send heartbeat.** The bridge posts `{"device_id":"DEV001"}` with the
   matching `X-Device-Key` header to `/api/device-monitoring/heartbeat`.
5. **Validate and update.** The backend checks the key, registered state, and
   active room. If valid, it records the backend's current UTC time in
   `last_communication_at` and sets `current_status` to `ONLINE`.
6. **Record transitions.** If status changed (for example `UNKNOWN` to
   `ONLINE`, or `OFFLINE` to `ONLINE`), one `device_status_log` row is added
   with the previous/new states, timestamp, and reason `HEARTBEAT`. Repeated
   heartbeats while already online update the timestamp but do not add duplicate
   transition rows.
7. **Detect a timeout.** A scheduled operator task runs the backend CLI
   reconciliation command. A registered, online device with a last heartbeat
   at or before the timeout cutoff is changed to `OFFLINE`, with a history row
   whose reason is `HEARTBEAT_TIMEOUT`.
8. **Recover.** The next valid heartbeat changes `OFFLINE` back to `ONLINE` and
   writes a new `HEARTBEAT` transition row.

A device that has never sent a heartbeat remains `UNKNOWN`: reconciliation only
marks devices offline when they are currently `ONLINE` and have a recorded
`last_communication_at`.

Deactivation is a separate lifecycle operation from connectivity detection.
The current device deactivation code changes `registration_status` to
`DEACTIVATED`; room deactivation also deactivates its assigned device. These
operations do not change `current_status` or add a device-status history row.
Consequently, a deactivated device can retain its last `ONLINE` value in the
all-devices status endpoint, although it is excluded from the dashboard summary
and cannot send accepted heartbeats. This is existing behavior, not an offline
transition.

## Online and offline timeout configuration

`DEVICE_HEARTBEAT_TIMEOUT_SECONDS` is read from the environment when the Flask
app is created. It must be a positive integer; the default is `120` seconds.
Choose a timeout longer than the expected heartbeat interval, with enough room
for LoRa and network delays. For example, if a Node reports once per minute,
the timeout should exceed 60 seconds to avoid marking it offline during normal
latency.

Offline detection is **not** run by a Flask background thread and is not
triggered by opening the dashboard. The CLI command is:

```powershell
flask --app server reconcile-device-status
```

Configure Windows Task Scheduler or the deployment's scheduler to run this
command repeatedly (for example, every 30 seconds with a 120-second timeout).
Without that recurring task, the database can keep showing `ONLINE` after a
device stops communicating. Reconciliation is safe to repeat: it only writes a
history row when it changes an `ONLINE` device to `OFFLINE`.

## Other device API calls

The occupancy API uses the same device key in `X-Device-Key`:

```http
POST /api/occupancy/events
Content-Type: application/json
X-Device-Key: <plaintext-device-key>

{"room_id":1,"device_id":"DEV001","event_type":"MOTION_DETECTED","occupancy_status":"OCCUPIED"}
```

It additionally checks that the device belongs to the supplied room and that
the room is active. Heartbeat and occupancy reporting are separate requests:
an occupancy event updates occupancy state, while a heartbeat updates device
communication time/status.

Administrator JWT-protected monitoring endpoints are:

| Method | Endpoint | Purpose |
| --- | --- | --- |
| `GET` | `/api/device-monitoring/summary` | Dashboard counts: registered, active, online, offline, and unknown devices |
| `GET` | `/api/device-monitoring/devices/status` | Current status and last communication for all devices |
| `GET` | `/api/device-monitoring/devices/<device_id>/status` | Current status for one device |
| `GET` | `/api/device-monitoring/devices/<device_id>/history` | Recent status transitions; optional `limit` from 1 to 500 |

The summary's `active_count` and availability counts include registered devices
assigned to active rooms. `registered_count` includes registered devices even
if their room is inactive. The monitoring read endpoints do not run timeout
reconciliation themselves, so online/offline dashboard counts reflect the most
recent reconciliation run.

## Relevant implementation files

- `services/security/device_keys.py` — key generation, digest storage, and
  operator provisioning.
- `services/security/device_auth.py` — shared request-key verification and
  registration check.
- `api/device_monitoring/routes.py` — heartbeat and administrator monitoring
  endpoints.
- `services/device/heartbeat.py` — heartbeat state/timestamp transaction.
- `services/device/monitoring.py` — timeout reconciliation, status queries, and
  dashboard counts.
- `database/models/room_device.py` — stored credential digest and current
  communication state.
- `database/models/device_status_log.py` — status transition history.
- `cli.py` — `rotate-device-key` and `reconcile-device-status` commands.
- `database/__init__.py` — `DEVICE_HEARTBEAT_TIMEOUT_SECONDS` configuration.
