# Proposed Gateway broadcast contract (review required)

The pending-work and dispatch routes below remain proposals for Marckie (EG-4)
and are not registered. The acknowledgment route is implemented under the
provisional BE-4 contract, pending Gateway team review. The system design calls
for Room Node identification, Gateway-to-backend communication, and stored
notification acknowledgments, but does not specify the HTTP interface.

## Authentication and scope

Reuse the existing per-device `X-Device-Key` credential. The Gateway supplies
the `device_id` for the Room Node it is serving. The backend authenticates that
device and returns or updates only broadcast targets for its assigned `room_id`.
An invalid key is denied; a valid key for another room cannot access this
target. The Gateway must poll separately for each provisioned device.

## Pending work

Proposed `GET /api/gateway/devices/{device_id}/emergency-broadcasts/pending`
with `X-Device-Key: <device key>` and no request body. The backend returns only
targets with `delivery_status == "PENDING"` for the authenticated device's
room. Reading the feed does not change delivery status or claim work.

```json
{
  "items": [
    {
      "broadcast_id": 12,
      "target_id": 34,
      "room_id": 5,
      "device_id": "DEV005",
      "message_text": "Evacuate now"
    }
  ]
}
```

`device_id` is the proposed routing identity. The backend includes `room_id`
to identify the persisted broadcast-room pair. The Gateway maps `device_id`
to its radio identity using its existing device inventory.

## Dispatch report

Proposed `POST /api/gateway/devices/{device_id}/emergency-broadcasts/{broadcast_id}/dispatch`
with `X-Device-Key: <device key>` and no request body. The server derives
`room_id` from the authenticated device. The Gateway sends this report only
after its radio transmit operation reports that it sent the frame for that
Room Node. That report moves the matching target from `PENDING` to
`DISPATCHED`; it does not mean the Room Node received the message. Fetching
pending work alone leaves it `PENDING`.

The backend performs an atomic update conditional on that exact
`(broadcast_id, room_id)` being `PENDING`. A repeated report for an already
`DISPATCHED` target succeeds without changing its original `dispatched_at`.
A report for an `ACKNOWLEDGED` or `FAILED` target leaves that terminal status
untouched. A broadcast-room pair that was never targeted is not created.
Room Node acknowledgment remains in BE-4.

## Room Node acknowledgment (implemented provisionally)

After the Room Node confirms receipt, the Gateway calls:

```http
POST /api/gateway/emergency-broadcasts/12/acknowledgments HTTP/1.1
Content-Type: application/json
X-Device-Key: <credential for DEV005>

{"device_id":"DEV005"}
```

The backend validates the credential against `device_id`, requires a
registered Room Node, and derives `room_id` from that device's existing
`RoomDevice` assignment. A caller-supplied `room_id` is rejected and cannot
authorize an acknowledgment. The backend updates only the existing
`(broadcast_id, room_id)` target; it never creates a target here.

Successful response (`200`):

```json
{
  "broadcast_id": 12,
  "room_id": 5,
  "device_id": "DEV005",
  "delivery_status": "ACKNOWLEDGED",
  "acknowledged_at": "2026-11-13T10:00:00+00:00"
}
```

`PENDING` and `DISPATCHED` targets become `ACKNOWLEDGED`. This accepts a Room
Node confirmation even if the dispatch report arrives late. A repeated
acknowledgment returns `200` with the original `acknowledged_at`. `FAILED` is
final under this provisional contract and returns `409`. A later dispatch
report cannot overwrite `ACKNOWLEDGED`.

Malformed JSON, a missing or invalid `device_id`, and unsupported fields
return `400`. Missing or incorrect device credentials return `401`; an
unregistered device returns `403`. An unknown broadcast or a broadcast that
did not target the authenticated device's room returns `404`. The Gateway
team must verify this behavior with an actual Room Node and Gateway.

## Decisions for EG-4

Marckie and the backend team need to confirm:

1. Whether per-device keys and polling once per provisioned device fit the
   Gateway, or whether a separate Gateway credential and global feed are
   needed.
2. Whether `device_id` is the correct radio-routing identity, and how to
   handle a room with no assigned, registered device. Broadcast creation
   currently accepts active rooms without requiring a device or an online
   status.
3. Whether a successful radio transmit operation is the correct dispatch
   event, including how the Gateway handles a restart after transmission but
   before its dispatch report.
4. Whether an inactive room should be rejected at creation, as the earlier
   BE-3 draft and current creation flow do.
5. Review the provisional acknowledgment route, per-device credential,
   device-to-room mapping, and `PENDING`/`FAILED` transition rules against
   the actual Room Node confirmation message.
