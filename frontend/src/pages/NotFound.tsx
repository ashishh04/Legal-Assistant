import { useLocation, useNavigate } from "react-router-dom";
import { ArrowLeft, Compass } from "lucide-react";
import { Button, EmptyState } from "../components/ui";

export default function NotFound() {
  const navigate = useNavigate();
  const { pathname } = useLocation();
  return (
    <div className="mx-auto max-w-xl pt-10">
      <EmptyState icon={Compass} title="This page doesn't exist"
        action={<Button icon={ArrowLeft} onClick={() => navigate("/")}>Back to the overview</Button>}>
        There is nothing at <span className="font-mono text-[12.5px]">{pathname}</span>. Check the address, or use the menu.
      </EmptyState>
    </div>
  );
}
