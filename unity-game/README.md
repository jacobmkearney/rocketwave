## Unity Project Layout (Rocket POC)

Recommended: keep the Unity project in this repository under `unity-game/`.

### Getting Started
1. In Unity Hub, create a new 2D (URP or Core) project and set the location to this folder: `unity-game/`.
   - Unity will populate `Assets/`, `ProjectSettings/`, etc.
2. Copy the provided scripts into `Assets/Scripts/`:
   - `Assets/Scripts/UdpRelaxationReceiver.cs`
   - `Assets/Scripts/RocketController.cs`

### Scene Setup
1. Create a Scene `RocketPOC`.
2. GameObjects:
   - `SignalReceiver` (empty) → add `UdpRelaxationReceiver` (port 5005)
   - `Rocket` (sprite) → add `RocketController`; assign `SignalReceiver` to `receiver`
3. Optional: add a UI element to visualize `Relaxation01`.

### Run
1. Start the Python sender in a terminal (from repo root):
```bash
uv run rocketwave-log
```
2. Press Play in Unity. The rocket should climb faster with higher relaxation and reset on sustained low values.

### Troubleshooting
- If no data arrives, verify UDP locally:
```bash
nc -ul 5005 | cat
```
- Ensure macOS Firewall allows Unity Editor to receive network traffic.
- Change port in both Python and `UdpRelaxationReceiver` if 5005 is busy.


