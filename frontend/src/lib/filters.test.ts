import { describe, expect, it } from "vitest";
import { filterQuery, investigateHref } from "./filters";

describe("investigateHref preserves context", () => {
  it("carries target, filters and a return path", () => {
    const href = investigateHref(
      { series: "claimant_rate", geo: "E12000002", period: "2026-09" },
      { pathname: "/regions", search: "geo=E12000002&from=2020&sector=C" },
    );
    const u = new URL(href, "http://x");
    expect(u.pathname).toBe("/investigate");
    expect(u.searchParams.get("series")).toBe("claimant_rate");
    expect(u.searchParams.get("geo")).toBe("E12000002");
    expect(u.searchParams.get("period")).toBe("2026-09");
    expect(u.searchParams.get("from")).toBe("2020");
    expect(u.searchParams.get("sector")).toBe("C");
    expect(u.searchParams.get("return")).toBe("/regions?geo=E12000002&from=2020&sector=C");
  });
  it("omits the total dimension and passes the filter geography as a hint", () => {
    const u = new URL(investigateHref({ series: "cpi_yoy", dim: "_" }, { pathname: "/", search: "geo=E12000007" }), "http://x");
    expect(u.searchParams.has("dim")).toBe(false);
    expect(u.searchParams.get("fgeo")).toBe("E12000007");
  });
});

describe("filterQuery", () => {
  it("keeps only global filters", () => {
    const sp = new URLSearchParams("from=2015&geo=E12000001&series=x&tab=y");
    expect(filterQuery(sp)).toBe("from=2015&geo=E12000001");
  });
});
