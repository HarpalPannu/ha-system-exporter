# Home Assistant System Metrics Exporter Custom Integration

This custom integration fetches system metrics from the lightweight Go System Metrics Exporter API and integrates them natively as Home Assistant entities.

## Features
- **UI Integration Setup:** Add, configure, and validate host details directly through Home Assistant's Settings UI (Config Flow).
- **10 Core Sensors:** Exposes CPU Load, CPU Temp, RAM Available, Uptime, System Load (1m, 5m, 15m), Disk Usage, and Network speeds (RX/TX).
- **Home Assistant Friendly:** Integrates natively using device classes (like `timestamp` for uptime, `temperature` for CPU temp), and provides custom icons.

---

## Installation via HACS

To add this integration using HACS (Home Assistant Community Store):

### 1. Add Custom Repository to HACS
1. In Home Assistant, navigate to **HACS** -> **Integrations**.
2. Click the three dots in the top right corner and select **Custom repositories**.
3. In the dialog:
   - **Repository:** Enter the URL of this Git repository (e.g., `https://github.com/<your-username>/ha-system-exporter`).
   - **Category:** Select **Integration**.
4. Click **Add**.

### 2. Download the Integration
1. Click on the newly added **System Metrics Exporter Integration** card.
2. Click **Download** in the bottom right corner.
3. Restart Home Assistant to load the component.

---

## Setup & Configuration

1. In Home Assistant, go to **Settings** -> **Devices & Services**.
2. Click the **Add Integration** button in the bottom right corner.
3. Search for **System Metrics Exporter** and select it.
4. Enter the URL of your Go System Exporter API (e.g., `http://192.168.1.50:8080`).
5. Click **Submit** to verify the connection and register all sensors!
