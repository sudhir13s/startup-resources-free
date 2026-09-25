"use client";

import { useState } from "react";
import { useRouter } from "next/navigation";
import { LogOut } from "lucide-react";
import { Button } from "@/components/ui/button";

export function LogoutButton() {
  const router = useRouter();
  const [loggingOut, setLoggingOut] = useState(false);

  async function handleLogout() {
    setLoggingOut(true);
    try {
      await fetch("/api/auth/logout", { method: "POST" });
    } finally {
      router.push("/login");
    }
  }

  return (
    <Button
      type="button"
      variant="outline"
      size="icon"
      aria-label="Log out"
      title="Log out"
      onClick={() => void handleLogout()}
      disabled={loggingOut}
      className="h-9 w-9"
    >
      <LogOut className="h-4 w-4" />
    </Button>
  );
}
