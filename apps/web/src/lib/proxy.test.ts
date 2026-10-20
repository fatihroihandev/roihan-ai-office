import { describe, expect, it } from "vitest";
import { buildUpstreamUrl } from "./proxy";

const base = "http://127.0.0.1:8000";

describe("buildUpstreamUrl", () => {
  it("menyusun URL tanpa segmen tambahan", () => {
    expect(buildUpstreamUrl(base, "api/projects", [], "")).toBe(`${base}/api/projects`);
  });

  it("menyusun URL bersarang beserta query", () => {
    expect(buildUpstreamUrl(base + "/", "api/projects", ["abc-1", "files"], "?kind=asset")).toBe(
      `${base}/api/projects/abc-1/files?kind=asset`,
    );
  });

  it("menolak traversal dan karakter berbahaya", () => {
    for (const bad of ["..", ".", "", "a/b", "a%2fb", "a b", "a?b", "a#b", "../health"]) {
      expect(buildUpstreamUrl(base, "api/projects", [bad], ""), bad).toBeNull();
    }
  });
});
