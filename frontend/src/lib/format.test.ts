import { describe, expect, it } from "vitest";
import { fmtChange, fmtCompact, fmtValue, obsTime } from "./format";

describe("fmtValue keeps units with values", () => {
  it("percent and pp", () => {
    expect(fmtValue(3.5, "%", 1)).toBe("3.5%");
    expect(fmtChange(0.4, "pp")).toBe("+0.40pp");
    expect(fmtChange(-1.25, "%", 1)).toBe("−1.3%");
  });
  it("£m switches to £bn above £1,000m", () => {
    expect(fmtValue(744453, "£m")).toBe("£744.5bn");
    expect(fmtValue(920, "£m")).toBe("£920m");
    expect(fmtValue(-24520, "£m")).toBe("£-24.5bn");
  });
  it("prices and indices", () => {
    expect(fmtValue(174.57, "pence per litre", 1)).toBe("174.6p/l");
    expect(fmtValue(103.3, "index (2015=100)", 1)).toBe("103.3");
    expect(fmtValue(550340, "£", 0)).toBe("£550,340");
  });
  it("missing values are an explicit dash, never zero", () => {
    expect(fmtValue(null, "%")).toBe("–");
    expect(fmtValue(Number.NaN, "£m")).toBe("–");
    expect(fmtChange(undefined, "pp")).toBe("–");
  });
  it("compact numbers", () => {
    expect(fmtCompact(1_545_100)).toBe("1.5m");
    expect(fmtCompact(36_733_961)).toBe("36.7m");
  });
});

describe("obsTime", () => {
  it("uses the period key for half-hourly data", () => {
    expect(obsTime({ period: "2026-10-26T12:30Z", period_start: "2026-10-26" }, "HH")).toBe("2026-10-26T12:30:00Z");
    expect(obsTime({ period: "2026-09", period_start: "2026-09-01" }, "M")).toBe("2026-09-01");
  });
});
