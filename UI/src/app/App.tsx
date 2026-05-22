import { RouterProvider } from "react-router";
import { router } from "./routes";

export default function App() {
  return (
    <div className="w-full h-full">
      <RouterProvider router={router} />
    </div>
  );
}