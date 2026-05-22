import { createBrowserRouter } from "react-router";
import SetupPage from "./pages/SetupPage";
import ScanPage from "./pages/ScanPage";
import ThinkingPage from "./pages/ThinkingPage";
import DashboardPage from "./pages/DashboardPage";

export const router = createBrowserRouter([
  {
    path: "/",
    Component: SetupPage,
  },
  {
    path: "/scan",
    Component: ScanPage,
  },
  {
    path: "/thinking",
    Component: ThinkingPage,
  },
  {
    path: "/dashboard",
    Component: DashboardPage,
  },
]);
