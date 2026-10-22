import { describe, expect, it } from "vitest";
import { agentsForPower, availableAction, isTransitional, pollInterval, resolutionsFor } from "./power";

describe("availableAction", () => {
  it("OFF saat berjalan, ON saat berhenti, tidak ada aksi saat transisi", () => {
    expect(availableAction({ state: "RUNNING", scheduling: true })).toBe("off");
    expect(availableAction({ state: "PAUSED", scheduling: false })).toBe("on");
    expect(availableAction({ state: "ERROR", scheduling: false })).toBe("on");
    expect(availableAction({ state: "PAUSING", scheduling: false })).toBeNull();
    expect(availableAction({ state: "RESUMING", scheduling: false })).toBeNull();
  });
  it("RECOVERY_REQUIRED mengikuti apakah scheduler masih berjalan", () => {
    expect(availableAction({ state: "RECOVERY_REQUIRED", scheduling: true })).toBe("off");
    expect(availableAction({ state: "RECOVERY_REQUIRED", scheduling: false })).toBe("on");
  });
});

describe("polling", () => {
  it("lebih cepat saat transisi", () => {
    expect(isTransitional("PAUSING")).toBe(true);
    expect(isTransitional("RUNNING")).toBe(false);
    expect(pollInterval("RESUMING")).toBeLessThan(pollInterval("RUNNING"));
  });
});

describe("agentsForPower", () => {
  const agents = [{ role: "a", status: "working" }, { role: "b", status: "error" }, { role: "c", status: "idle" }];
  it("PAUSED: semua istirahat kecuali error", () => {
    expect(agentsForPower(agents, "PAUSED").map((a) => a.status)).toEqual(["idle", "error", "idle"]);
  });
  it("status lain tidak mengubah apa pun dan tidak memutasi input", () => {
    expect(agentsForPower(agents, "RUNNING")).toBe(agents);
    expect(agentsForPower(agents, undefined)).toBe(agents);
    agentsForPower(agents, "PAUSED");
    expect(agents[0].status).toBe("working");
  });
});

describe("resolutionsFor", () => {
  it("pilihan sesuai jenis item; jenis tak dikenal tetap punya jalan keluar", () => {
    expect(resolutionsFor("external_unknown")).toEqual(["confirmed_not_done", "confirmed_done"]);
    expect(resolutionsFor("risky_task_interrupted")).toContain("requeue");
    expect(resolutionsFor("baru").length).toBeGreaterThan(0);
  });
});
