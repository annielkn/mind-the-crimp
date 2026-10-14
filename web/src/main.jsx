import React from "react";
import { createRoot } from "react-dom/client";
import App from "./App.jsx";
import "./App.css";
import { mountFooter } from "./nav.js";

createRoot(document.getElementById("root")).render(<App />);
mountFooter();
