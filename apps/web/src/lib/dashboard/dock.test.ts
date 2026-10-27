import { describe, expect, it } from "vitest";
import { DOCK, NAV_GROUPS, VIEW_IDS, VIEW_META } from "./dock";

describe("Addendum v2.4 Sidebar Navigation & Dock Metadata", () => {
  it("groups all 10 canonical marketing modules into logical groups without engineering menus", () => {
    expect(DOCK.length).toBe(10);
    const groupKeys = new Set(NAV_GROUPS.map((g) => g.key));
    for (const item of DOCK) {
      expect(groupKeys.has(item.group)).toBe(true);
      expect(item.title.toLowerCase()).not.toContain("engineering");
      expect(item.title.toLowerCase()).not.toContain("coding");
      // Uses clean SVG icon identifiers rather than emojis
      expect(/^[a-z]+$/.test(item.icon)).toBe(true);
    }
  });

  it("provides complete breadcrumb & title metadata for every view ID", () => {
    for (const id of VIEW_IDS) {
      expect(VIEW_META[id]).toBeDefined();
      expect(VIEW_META[id].title.length).toBeGreaterThan(2);
      expect(VIEW_META[id].groupLabel.length).toBeGreaterThan(2);
    }
  });
});
