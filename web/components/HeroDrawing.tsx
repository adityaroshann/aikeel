"use client";

import { useEffect, useState } from "react";
import Drawing from "./Drawing";
import { check, getWorkspaces, type CheckResult } from "@/lib/api";

export default function HeroDrawing() {
  const [data, setData] = useState<CheckResult | null>(null);
  const [failed, setFailed] = useState(false);

  useEffect(() => {
    getWorkspaces()
      .then(({ workspaces }) => {
        const yard = workspaces.find((w) => w.id === "yard_a");
        if (!yard?.seed_profile) throw new Error("no seed");
        return check({ workspace: "yard_a" }, yard.seed_profile);
      })
      .then(setData)
      .catch(() => setFailed(true));
  }, []);

  if (data) return <Drawing data={data} interactive={false} className="border-x-0 border-b-0 border-t-2" />;
  return (
    <div className="film-grid flex aspect-[104/27] items-center justify-center border-t-2 border-ink text-sm text-steel">
      {failed ? "The live drawing is unavailable right now. Open the demo to try again." : "Loading the live drawing…"}
    </div>
  );
}
