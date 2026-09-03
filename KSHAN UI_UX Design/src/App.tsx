import { useState } from "react";
import GuestScreens from "./screens/GuestScreens";
import StudioScreens from "./screens/StudioScreens";

const guest = ["home", "find-event", "event-landing", "selfie-capture", "selfie-confirm", "searching", "results", "photo-selection", "photo-viewer", "no-results", "event-gallery"];
const studio = ["login", "dashboard", "events", "create-event", "event-workspace", "gallery", "bulk-upload", "processing", "people", "share-event", "qr-poster", "guest-activity", "settings"];
const labels: Record<string, string> = {
  home: "Homepage", "find-event": "Find event", "event-landing": "Event landing", "selfie-capture": "Selfie capture", "selfie-confirm": "Confirm selfie", searching: "Searching", results: "Your photos", "photo-selection": "Selections", "photo-viewer": "Photo viewer", "no-results": "No results", "event-gallery": "Event gallery",
  login: "Studio login", dashboard: "Dashboard", events: "Events", "create-event": "Create event", "event-workspace": "Workspace", gallery: "Gallery manager", "bulk-upload": "Bulk upload", processing: "Processing", people: "People", "share-event": "Share event", "qr-poster": "QR poster", "guest-activity": "Guest activity", settings: "Settings",
};

export default function App() {
  const [area, setArea] = useState<"guest" | "studio">("guest");
  const [screen, setScreen] = useState("home");
  const go = (next: string) => { setArea(guest.includes(next) ? "guest" : "studio"); setScreen(next); };
  const active = area === "guest" ? guest : studio;

  return <div className="app-canvas">
    <header className="preview-bar">
      <span className="preview-brand">KSHAN</span>
      <div className="preview-select">
        <button className={area === "guest" ? "active" : ""} onClick={() => go("home")}>Guest experience</button>
        <button className={area === "studio" ? "active" : ""} onClick={() => go("dashboard")}>Studio workspace</button>
      </div>
      <select className="screen-picker" value={screen} onChange={e => go(e.target.value)} aria-label="Choose preview screen">
        {active.map(id => <option key={id} value={id}>{labels[id]}</option>)}
      </select>
    </header>
    {area === "guest" ? <GuestScreens screen={screen} navigate={go} /> : <StudioScreens screen={screen} navigate={go} />}
  </div>;
}
