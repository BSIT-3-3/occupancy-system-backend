# Next Sprint Plan
## Sprint goal

Connect one Room Node and Gateway to the backend flows that already exist,
close the assistance-request authentication gap, provide required occupancy
event history, and deliver the confirmed emergency-broadcast flow. Verify
existing desktop integrations before scheduling new UI work.

This plan is based on the backend repository. The C# desktop and embedded/Gateway
source code were not available for review, so completion of their integrations
cannot be confirmed here. Those tasks focus on verifying and closing actual
gaps, not rebuilding work that may already be complete.

## 1. Backend Developers (BE)

| Task number | Task name | Assigned member
|---|---|---|
| BE-1 | Secure assistance-request creation | Puyos 
| BE-2 | Occupancy event history | Cristian 
| BE-3 | Emergency-broadcast API and persistence | Concepption 
| BE-4 | Broadcast delivery status and acknowledgment endpoint | Medina 
### BE-1 — Secure assistance-request creation (Puyos)

**Objective:** Ensure that a device can create an assistance request only when
it authenticates as the registered device assigned to the specified room.

**Implementation details:** Require the device credential header and use the
existing device-authentication service for `POST /assistance-requests`. Check
the device and room association, and reject inactive or unregistered devices
consistently with heartbeat and occupancy behavior. Confirm that staff-facing
list, detail, and status-update operations have the intended administrator
access protection. Preserve the existing pending → acknowledged → resolved
workflow and timestamps.

**Expected outcome:** Requests from a valid assigned device are stored and can
be handled by authorized staff. Missing or invalid credentials and mismatched
room assignments are rejected. Existing request data and status behavior remain
compatible.

### BE-2 — Occupancy event history (Cristian)

**Objective:** Provide the desktop with the required history of occupancy
events, in addition to the room's current status.

**Implementation details:** Add a small administrator-protected read endpoint
for occupancy events, ordered newest first and bounded by a sensible limit.
Return the event fields already stored by the `OccupancyEvent` model. Do not
add filtering or analytics the UI does not need.

**Expected outcome:** The desktop can display recent occupancy events from
persisted records, alongside the current room state.

### BE-3 — Minimal emergency-broadcast API and persistence (Concepption)

**Objective:** Support the confirmed emergency-broadcast behavior: an
administrator sends a message through the desktop application, and each
target Room Node displays that message and activates its buzzer.

**Implementation details:** Define and persist a broadcast message and its
target rooms. Provide the desktop with an administrator-protected way to
create/send it, and provide the Gateway with the agreed way to retrieve
pending work for transmission. Carry the message text and target identity to
the node so it can display the message and activate its buzzer. Represent only
the lifecycle needed by the scenario: created/pending, dispatched, and
acknowledged or failed per target room. Validate target rooms and agree API
paths and payloads with the Gateway and desktop before implementation. Do not
add a general command framework, scheduling, or unrelated message types.

**Expected outcome:** An administrator can send a message to selected rooms
from the desktop; the Gateway can retrieve it for transmission; target nodes
display it and activate their buzzers; and the backend retains delivery state
for the desktop.

### BE-4 — Broadcast delivery status and acknowledgment endpoint (Medina)

**Objective:** Record whether each targeted room received a broadcast so the
desktop can show useful delivery results.

**Implementation details:** Add the minimal per-room delivery state and a
Gateway-facing acknowledgment operation. Validate that acknowledgments refer
to an existing broadcast and target room. Make repeated acknowledgments safe
to process, and expose the resulting status to authorized desktop users. Keep
this tied to broadcasts; do not build a general communication logging API.

**Expected outcome:** Each target room has a visible, persisted delivery result
that the desktop can display.

## 2. Embedded / Gateway Developers

| Task number | Task name | Assigned member 
|---|---|---
| EG-1 | Confirm the LoRa message fields| Helli 
| EG-2 | Connect one Room Node to the Gateway | Gio 
| EG-3 | Verify Gateway integration with existing backend endpoints | Janus 
| EG-4 | Support broadcast retrieval, transmission, and acknowledgments | Marckie
| EG-5 | Validate one-node hardware integration | all embbeded team 

### EG-1 — Confirm the LoRa message fields (Helli)

**Objective:** Agree on the smallest radio payload contract needed for
occupancy, assistance, emergency broadcast, and acknowledgment.

**Implementation details:** Document message type, device identity, required
values, and how the Gateway maps radio identities to backend device IDs.
Include only fields used by these workflows, and align the Gateway-to-backend
mapping with the existing authenticated heartbeat and occupancy contracts.

**Expected outcome:** Room Node, Gateway, backend, and desktop teams share a
short, implementable contract before cross-component integration.

### EG-2 — Connect one Room Node to the Gateway (Gio)

**Objective:** Demonstrate that one representative Room Node can send the
pilot messages and receive the applicable Gateway response.

**Implementation details:** Integrate the agreed LoRa message format for
occupancy, assistance, and broadcast. Implement node behavior to display the
received broadcast message and activate its buzzer, then acknowledge receipt.

**Expected outcome:** One node can participate in the end-to-end pilot flow
over the actual radio link.

### EG-3 — Verify Gateway integration with existing backend endpoints (Janus)

**Objective:** Verify that the Gateway forwards Room Node events to backend
operations that are already implemented, rather than rebuilding those APIs.

**Implementation details:** Verify integration with the existing heartbeat
and occupancy endpoints; do not rebuild them. Map radio identity to the
correct device ID and credential and call those endpoints over the configured
backend connection. Forward assistance requests after the backend
authentication change is available. Handle backend responses and surface
success or failure to the Gateway's local flow. Keep credentials out of
payloads and logs.

**Expected outcome:** A valid node can update backend connectivity and room
occupancy, and an assistance request reaches the backend under the correct
device identity.

### EG-4 — Support broadcast retrieval, transmission, and acknowledgments (Marckie)

**Objective:** Complete the Gateway side of the confirmed broadcast lifecycle.

**Implementation details:** Retrieve pending broadcasts using the agreed
backend contract, transmit the message and target identity to Room Nodes, and
ensure the target node displays the message and activates its buzzer. Submit
per-room delivery acknowledgments. Keep polling and acknowledgment behavior
limited to the defined broadcast workflow; do not implement a generic command
bus.

**Expected outcome:** A message sent from the desktop reaches its target Room
Node, is displayed with the buzzer activated, and its delivery result returns
to the backend.

### EG-5 — Validate one-node hardware integration (All)

**Objective:** Confirm the radio and Gateway behavior on real hardware before
expanding to additional rooms.

**Implementation details:** Exercise the agreed pilot messages with one Room
Node and the Gateway. Record the device and room used, observed message flow,
and any hardware or signal issue that blocks the scenario.

**Expected outcome:** One physical node can complete occupancy and assistance
flows and, for broadcast, display the message and activate the buzzer.

## 3. Desktop Developers (C#)

| Task number | Task name | Assigned member
|---|---|---
| UI-1 | Verify existing device monitoring and history integration |Budol / Paolo
| UI-2 | Verify current room occupancy display | Abala 
| UI-3 | Verify assistance request handling | Miguel
| UI-4 | Connect emergency broadcast creation and delivery status | Budol / Paolo

### UI-1 — Verify existing device monitoring and history integration (Budol / Paolo)

**Objective:** Confirm the desktop uses the backend device monitoring and
history APIs that are already implemented.

**Implementation details:** Check device summary, current status, last
communication, and status-history screens against the existing endpoints. Fix
only actual connection, response mapping, or display gaps. Do not create
duplicate backend monitoring work.

**Expected outcome:** Device status and history are usable in the desktop, or
any remaining concrete gap is documented with a reproducible example.

### UI-2 — Verify current room occupancy display (Abala)

**Objective:** Confirm the desktop displays the room state written by the
existing occupancy event endpoint.

**Implementation details:** Connect or correct the screen's use of current
room occupancy and verify its refresh behavior. Add the required event-history
display using BE-2.

**Expected outcome:** A backend occupancy update becomes visible in the room
view without requiring a duplicate occupancy API.

### UI-3 — Verify assistance request handling (Miguel)

**Objective:** Complete the staff-facing portion of the existing assistance
workflow.

**Implementation details:** Confirm pending requests appear and staff can
acknowledge and resolve them using the existing request endpoints. Update
authentication or error handling only where required by the secured backend
contract.

**Expected outcome:** Staff can see and progress an authenticated device's
request through the existing statuses.

### UI-4 — Connect emergency broadcast creation and delivery status (Budol / Paolo)

**Objective:** Let an administrator send a broadcast from the desktop and see
delivery results.

**Implementation details:** Use the minimal create and status contracts from
BE-3 and BE-4. Keep the UI to message entry, target selection, submission
result, and per-room delivery status. Clearly communicate that a target Room
Node displays the message and activates its buzzer.

**Expected outcome:** The desktop can send the defined message and display its
persisted per-room delivery state without a separate communication-log feature.

## 4. Integration checks — Shared responsibility

| Task number | Task name | Assigned member 
|---|---|---
| IT-1 | Occupancy end-to-end check | All teams 
| IT-2 | Assistance request end-to-end check | BE + Embedded + Desktop 
| IT-3 | Emergency broadcast end-to-end check | BE + Embedded + Desktop

### IT-1 — Occupancy end-to-end check (All teams)

**Objective:** Verify the actual pilot path from a node to the desktop.

**Implementation details:** Exercise Room Node detection → LoRa Gateway receipt
→ existing authenticated backend occupancy endpoint → persisted event and
updated room status → desktop display. Capture failures at the component
boundary where they occur.

**Expected outcome:** One room's occupancy update is persisted and visible in
the desktop.

### IT-2 — Assistance request end-to-end check (BE + Embedded + Desktop)

**Objective:** Verify a complete request and staff response after device
authentication is enforced.

**Implementation details:** Exercise node request → Gateway forwarding with
the correct device identity → backend persistence → desktop pending display
→ staff acknowledgment and resolution.

**Expected outcome:** Only the assigned authenticated device can create the
request, and the desktop can progress it through the workflow.

### IT-3 — Emergency broadcast end-to-end check (BE + Embedded + Desktop)

**Objective:** Verify the confirmed broadcast behavior across components.

**Implementation details:** Exercise desktop message entry and sending →
backend target persistence → Gateway retrieval → LoRa transmission → target
node displays the message and activates its buzzer → node acknowledgment →
backend status update → desktop delivery display.

**Expected outcome:** Delivery state is visible per target room and reflects
the acknowledgment received through the real Gateway path.

