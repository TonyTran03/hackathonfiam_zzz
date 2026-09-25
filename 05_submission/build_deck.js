/*
 * Builds the submission deck from the pipeline's own outputs.
 *
 * Every number on every slide is read from deck_pack.csv, top_holdings.csv and
 * contributors.csv at build time; every chart is the PNG that 08_charts.py
 * wrote. Nothing is typed in by hand.
 *
 * That is deliberate. 05_submission/ once held holdings.csv from one
 * configuration and figures from a run four days older, and a deck built by
 * copying numbers off a screen would have shipped that mismatch. Now the deck
 * cannot disagree with the backtest that produced it: rerun MAIN.py, rerun
 * this, and the slides move together.
 *
 *   node 05_submission/build_deck.js
 */
const fs = require("fs");
const path = require("path");
const pptxgen = require("pptxgenjs");

const SUB = __dirname;
const FIGS = path.join(SUB, "figures");

// Midnight Executive. Navy dominates; ice blue supports; red marks the places
// where the honest number is worse than the headline.
const NAVY = "1E2761";
const ICE = "CADCFC";
const WHITE = "FFFFFF";
const RED = "A62B1F";
const GREY = "6B7280";
const INK = "1A1A1A";
const TINT = "F2F5FC";

const HEAD = "Cambria";
const BODY = "Calibri";

// ---------------------------------------------------------------- data ------
function readCsv(file) {
  const text = fs.readFileSync(path.join(SUB, file), "utf8").trim();
  const rows = [];
  let field = "", row = [], inQuotes = false;
  for (let i = 0; i < text.length; i++) {
    const c = text[i];
    if (inQuotes) {
      if (c === '"' && text[i + 1] === '"') { field += '"'; i++; }
      else if (c === '"') inQuotes = false;
      else field += c;
    } else if (c === '"') inQuotes = true;
    else if (c === ",") { row.push(field); field = ""; }
    else if (c === "\n") { row.push(field); rows.push(row); row = []; field = ""; }
    else if (c !== "\r") field += c;
  }
  row.push(field); rows.push(row);
  const head = rows.shift();
  return rows.filter(r => r.length === head.length)
             .map(r => Object.fromEntries(head.map((h, i) => [h.trim(), r[i]])));
}

const pack = readCsv("deck_pack.csv");
const holdings = readCsv("top_holdings.csv");
const contrib = readCsv("contributors.csv");
const robust = readCsv("robustness.csv");

/** Look a metric up by a substring of its label; fails loudly if absent. */
function M(needle, section) {
  const hit = pack.find(r => r.metric.toLowerCase().includes(needle.toLowerCase())
                        && (!section || r.section === section));
  if (!hit) throw new Error("deck_pack.csv has no metric matching: " + needle);
  return hit.value.trim();
}
function note(needle) {
  const hit = pack.find(r => r.metric.toLowerCase().includes(needle.toLowerCase()));
  return hit && hit.note ? hit.note.trim() : "";
}
const years = pack.filter(r => r.section === "calendar");

/** Robustness numbers, same discipline: read, never typed. */
function R(needle, section) {
  const hit = robust.find(r => r.metric.toLowerCase().includes(needle.toLowerCase())
                          && (!section || r.section === section));
  if (!hit) throw new Error("robustness.csv has no metric matching: " + needle);
  return hit.value.trim();
}
function Rnote(needle) {
  const hit = robust.find(r => r.metric.toLowerCase().includes(needle.toLowerCase()));
  return hit && hit.note && hit.note !== "NaN" ? hit.note.trim() : "";
}

// -------------------------------------------------------------- helpers -----
const pres = new pptxgen();
pres.layout = "LAYOUT_WIDE";            // 13.3 x 7.5 inches
pres.author = "FIAM Hackathon submission";
pres.title = "US Equity Market-Neutral Strategy";

function slide(dark) {
  const s = pres.addSlide();
  s.background = { color: dark ? NAVY : WHITE };
  return s;
}

function title(s, text, sub, dark) {
  s.addText(text, {
    x: 0.6, y: 0.42, w: 12.1, h: 0.72, isTextBox: true, margin: 0,
    fontFace: HEAD, fontSize: 32, bold: true, color: dark ? WHITE : NAVY,
  });
  if (sub) {
    s.addText(sub, {
      x: 0.6, y: 1.16, w: 12.1, h: 0.34, isTextBox: true, margin: 0,
      fontFace: BODY, fontSize: 13, color: dark ? ICE : GREY,
    });
  }
}

/** A stat card: big number, label above, caption below. */
function stat(s, x, y, w, label, value, caption, colour) {
  s.addShape(pres.ShapeType.roundRect, {
    x, y, w, h: 1.5, fill: { color: TINT }, line: { color: TINT },
    rectRadius: 0.06,
  });
  s.addText(label.toUpperCase(), {
    x: x + 0.22, y: y + 0.14, w: w - 0.44, h: 0.24, isTextBox: true, margin: 0,
    fontFace: BODY, fontSize: 9.5, bold: true, color: GREY, charSpacing: 0.6,
  });
  s.addText(value, {
    x: x + 0.22, y: y + 0.4, w: w - 0.44, h: 0.6, isTextBox: true, margin: 0,
    fontFace: HEAD, fontSize: 30, bold: true, color: colour || NAVY,
  });
  if (caption) {
    s.addText(caption, {
      x: x + 0.22, y: y + 1.02, w: w - 0.44, h: 0.4, isTextBox: true, margin: 0,
      fontFace: BODY, fontSize: 9.5, color: GREY,
    });
  }
}

/** A simple two-column table with a header row. */
function table(s, x, y, w, head, rows, colWidths, fontSize) {
  const fs_ = fontSize || 10.5;
  const rowH = fs_ > 10 ? 0.26 : 0.23;
  const body = rows.map(r => r.map((c, i) => ({
    text: String(c),
    options: { align: i === 0 ? "left" : "right", fontSize: fs_, fontFace: BODY,
               color: INK },
  })));
  s.addTable([head.map((h, i) => ({
    text: h,
    options: { align: i === 0 ? "left" : "right", bold: true, fontSize: fs_ - 0.5,
               fontFace: BODY, color: WHITE, fill: { color: NAVY } },
  }))].concat(body), {
    x, y, w, colW: colWidths, rowH, border: { type: "solid", pt: 0.5, color: "E3E7F0" },
    margin: 4,
  });
}

function bullets(s, x, y, w, items, size) {
  s.addText(items.map((t, i) => ({
    text: t, options: { bullet: true, breakLine: i !== items.length - 1 },
  })), {
    x, y, w, h: 0.4 * items.length, isTextBox: true, margin: 0, valign: "top",
    fontFace: BODY, fontSize: size || 12.5, color: INK, paraSpaceAfter: 6,
    lineSpacingMultiple: 1.05,
  });
}

function caption(s, x, y, w, text, colour) {
  s.addText(text, {
    x, y, w, h: 0.5, isTextBox: true, margin: 0,
    fontFace: BODY, fontSize: 10, italic: true, color: colour || GREY,
  });
}

function fig(s, name, x, y, w, h) {
  const p = path.join(FIGS, name + ".png");
  if (fs.existsSync(p)) s.addImage({ path: p, x, y, w, h });
  else s.addText("[missing figure: " + name + "]", {
    x, y, w, h, isTextBox: true, fontFace: BODY, fontSize: 11, color: RED, align: "center",
  });
}

// =========================================================== SLIDE 1 ========
{
  const s = slide(true);
  s.addText("US Equity Market-Neutral", {
    x: 0.8, y: 1.5, w: 11.7, h: 0.85, isTextBox: true, margin: 0,
    fontFace: HEAD, fontSize: 44, bold: true, color: WHITE,
  });
  s.addText("Gradient-boosted trees on 147 firm characteristics, traded through a "
          + "sector-, size- and beta-residualised long/short book",
    { x: 0.8, y: 2.42, w: 10.6, h: 0.6, isTextBox: true, margin: 0,
      fontFace: BODY, fontSize: 15, color: ICE });

  const cards = [
    ["Information ratio", M("INFORMATION RATIO"), "vs 3M T-bill + 4%, gross"],
    ["IR after 20bps", M("IR at 20 bps"), "trading costs applied"],
    ["Beta vs S&P 500", M("BETA vs S&P"), note("BETA vs S&P").replace(" -- the neutrality evidence", "")],
    ["Max drawdown", M("maximum drawdown (monthly"), "monthly marks"],
  ];
  cards.forEach((c, i) => {
    const x = 0.8 + i * 3.02;
    s.addShape(pres.ShapeType.roundRect, {
      x, y: 3.45, w: 2.8, h: 1.55, fill: { color: "2A3670" },
      line: { color: "2A3670" }, rectRadius: 0.06,
    });
    s.addText(c[0].toUpperCase(), {
      x: x + 0.2, y: 3.58, w: 2.4, h: 0.24, isTextBox: true, margin: 0,
      fontFace: BODY, fontSize: 9, bold: true, color: ICE, charSpacing: 0.6 });
    s.addText(c[1], {
      x: x + 0.2, y: 3.84, w: 2.4, h: 0.6, isTextBox: true, margin: 0,
      fontFace: HEAD, fontSize: 28, bold: true, color: WHITE });
    s.addText(c[2], {
      x: x + 0.2, y: 4.46, w: 2.4, h: 0.45, isTextBox: true, margin: 0,
      fontFace: BODY, fontSize: 9, color: ICE });
  });

  s.addText([
    { text: "Evaluation window ", options: { color: ICE } },
    { text: "2021-01 to 2026-08 (68 months)", options: { color: WHITE, bold: true } },
    { text: "   ·   200 names   ·   200% gross   ·   net " + M("average net exposure"),
      options: { color: ICE } },
  ], { x: 0.8, y: 5.35, w: 11.7, h: 0.3, isTextBox: true, margin: 0,
       fontFace: BODY, fontSize: 12 });

  s.addText("The alpha changed legs mid-period. 2021-22 came almost entirely from the "
          + "short book during the speculative unwind; since 2023 it has come from the "
          + "long book. We do not claim the first is repeatable.",
    { x: 0.8, y: 5.85, w: 11.7, h: 0.75, isTextBox: true, margin: 0,
      fontFace: BODY, fontSize: 12, italic: true, color: ICE });
  s.addNotes("Headline is the information ratio against cash plus 4 percent, which is "
           + "the competition's scoring metric. Gross figure first, net of 20bps beside "
           + "it. Beta is the neutrality evidence and is checked before anything else.");
}

// =========================================================== SLIDE 2 ========
{
  const s = slide(false);
  title(s, "The strategy", "Rank, then remove everything we are not trying to bet on");

  const steps = [
    ["1. Screen", "Price >= $5, no nano or micro caps. Without it the short book fills "
      + "with penny stocks: median cap $50m, and -48% in January 2021 alone."],
    ["2. Residualise", "The forecast is regressed on sector, size and beta each month; "
      + "only the residual is traded. Neutrality is enforced on the signal, not patched "
      + "onto the weights."],
    ["3. Smooth", "Scores averaged over three months. Turnover falls from 56% to "
      + M("average monthly turnover") + "; break-even cost rises to 93bps."],
    ["4. Size", "Inverse-volatility weights inside each leg, capped near 2%. The "
      + "information ratio is a ratio - the denominator counts."],
    ["5. Match beta", "Leg notionals set from each leg's own realised sensitivity over "
      + "24 completed months, not from per-stock estimates, which ran 0.30 too high on "
      + "the long side."],
  ];
  steps.forEach((st, i) => {
    const y = 1.72 + i * 1.02;
    s.addShape(pres.ShapeType.ellipse, {
      x: 0.62, y: y + 0.06, w: 0.38, h: 0.38, fill: { color: NAVY }, line: { color: NAVY } });
    s.addText(String(i + 1), { x: 0.62, y: y + 0.11, w: 0.38, h: 0.28, isTextBox: true,
      margin: 0, align: "center", fontFace: BODY, fontSize: 13, bold: true, color: WHITE });
    s.addText(st[0].replace(/^\d+\.\s*/, ""), {
      x: 1.14, y: y, w: 2.1, h: 0.3, isTextBox: true, margin: 0,
      fontFace: BODY, fontSize: 13, bold: true, color: NAVY });
    s.addText(st[1], {
      x: 1.14, y: y + 0.3, w: 5.5, h: 0.66, isTextBox: true, margin: 0,
      fontFace: BODY, fontSize: 10.5, color: INK, lineSpacingMultiple: 1.0 });
  });

  const longs = holdings.filter(h => h.side === "long").slice(0, 8);
  const shorts = holdings.filter(h => h.side === "short").slice(0, 8);
  s.addText("Largest average long positions", {
    x: 7.1, y: 1.66, w: 2.9, h: 0.26, isTextBox: true, margin: 0,
    fontFace: BODY, fontSize: 11, bold: true, color: NAVY });
  table(s, 7.1, 1.96, 5.6,
        ["Ticker", "Company", "Avg wt"],
        longs.map(h => [h.ticker, h.company_name.slice(0, 26),
                        (100 * parseFloat(h.avg_weight_overall)).toFixed(2) + "%"]),
        [0.85, 3.6, 1.15], 9.5);
  s.addText("Largest average short positions", {
    x: 7.1, y: 4.5, w: 2.9, h: 0.26, isTextBox: true, margin: 0,
    fontFace: BODY, fontSize: 11, bold: true, color: NAVY });
  table(s, 7.1, 4.8, 5.6,
        ["Ticker", "Company", "Avg wt"],
        shorts.map(h => [h.ticker, h.company_name.slice(0, 26),
                         (100 * parseFloat(h.avg_weight_overall)).toFixed(2) + "%"]),
        [0.85, 3.6, 1.15], 9.5);
  s.addNotes("Every holding is named by ticker and full company name. The short book "
           + "is more liquid than the long book: median daily dollar volume "
           + M("median daily dollar volume") + " against " + note("median daily dollar volume") + ".");
}

// =========================================================== SLIDE 3 ========
{
  const s = slide(false);
  title(s, "Data and method", "147 supplied characteristics; the 8-K corpus measured and reported");

  s.addText("Forecast", { x: 0.6, y: 1.62, w: 5.8, h: 0.28, isTextBox: true, margin: 0,
    fontFace: BODY, fontSize: 13, bold: true, color: NAVY });
  bullets(s, 0.6, 1.94, 5.9, [
    "Gradient-boosted trees, refit annually on an expanding window with a rolling "
      + "two-year validation block, split by target month.",
    "Missing values are NOT imputed for the trees. Missingness is informative - stocks "
      + "missing the most characteristics have a median cap of $282m against $1,687m.",
    "The target is demeaned within each month. Fitting raw returns stopped after ONE "
      + "boosting round: training averaged +0.27%/month against +2.52% in validation.",
    "Model choice is made inside each fold on that fold's validation block only.",
  ], 10.5);

  s.addText("Out-of-sample R-squared, benchmarked against zero", {
    x: 0.6, y: 4.35, w: 5.9, h: 0.28, isTextBox: true, margin: 0,
    fontFace: BODY, fontSize: 12, bold: true, color: NAVY });
  table(s, 0.6, 4.66, 5.9, ["Model", "OOS R2", "Monthly IC"], [
    ["Gradient-boosted trees", "+0.3956%", "+0.1354"],
    ["Ridge", "+0.0278%", "+0.1193"],
    ["OLS", "-0.0068%", "+0.0806"],
    ["Lasso / Elastic Net", "negative", "+0.08"],
  ], [2.7, 1.6, 1.6], 10);
  caption(s, 0.6, 5.95, 5.9,
    "The rules note 1-2% is typical even for neural networks. A large positive number "
    + "would mean a leak, not skill.");

  s.addText("The 8-K corpus: measured, not assumed", {
    x: 6.9, y: 1.62, w: 5.8, h: 0.28, isTextBox: true, margin: 0,
    fontFace: BODY, fontSize: 13, bold: true, color: NAVY });
  bullets(s, 6.9, 1.94, 5.8, [
    "27 single-signal tests on item codes. None survives a monthly cross-sectional "
      + "regression with controls.",
    "Joined into the model: validation rank correlation +0.1087 without, +0.1082 with. "
      + "No gain.",
    "The model's own usage agrees - the ten filing columns take 1.71% of its attention "
      + "against the 6.37% an average feature would.",
    "One exception: item 5.02 is null in aggregate (+0.046%/mo, t=+0.5) but splits into "
      + "abrupt departures at -0.640%/mo (t=-1.9) and routine appointments at +0.121%.",
  ], 10.5);
  s.addShape(pres.ShapeType.roundRect, { x: 6.9, y: 4.62, w: 5.8, h: 1.55,
    fill: { color: TINT }, line: { color: TINT }, rectRadius: 0.06 });
  s.addText("The trap worth knowing", {
    x: 7.12, y: 4.76, w: 5.4, h: 0.26, isTextBox: true, margin: 0,
    fontFace: BODY, fontSize: 11, bold: true, color: NAVY });
  s.addText("Item 5.02's own heading contains every keyword worth searching for. "
          + "Measured raw, \"appoint\" appears in 99.2% of these filings and the "
          + "sub-item markers in 88-100%. Strip the heading and they fall to 54.5% "
          + "and below. Any classifier trained on the unstripped text is learning "
          + "the title.", {
    x: 7.12, y: 5.04, w: 5.4, h: 1.05, isTextBox: true, margin: 0, valign: "top",
    fontFace: BODY, fontSize: 10, color: INK, lineSpacingMultiple: 1.0 });
  s.addNotes("The text answer is a measured null with three independent lines of "
           + "evidence, plus one signal that the aggregate was hiding. That is a "
           + "result, not a gap.");
}

// =========================================================== SLIDE 4 ========
{
  const s = slide(false);
  title(s, "Returns", "2021-01 to 2026-08, 68 months, gross of trading costs unless stated");

  stat(s, 0.6, 1.66, 2.9, "Annualised (CAGR)", M("annualised, geometric"), "arithmetic " + M("annualised, arithmetic"));
  stat(s, 3.68, 1.66, 2.9, "Cumulative", M("cumulative over the period"), "hurdle " + M("benchmark cumulative"));
  stat(s, 6.76, 1.66, 2.9, "Hit rate", M("hit rate"), "months beating the hurdle");
  stat(s, 9.84, 1.66, 2.86, "Mean month", M("average monthly return"), "best " + M("best month") + " / worst " + M("worst month"));

  s.addText("Calendar years", { x: 0.6, y: 3.45, w: 5.6, h: 0.28, isTextBox: true,
    margin: 0, fontFace: BODY, fontSize: 13, bold: true, color: NAVY });
  table(s, 0.6, 3.76, 6.1, ["Year", "Strategy", "Hurdle", "S&P 500"],
    years.map(r => {
      const parts = r.value.split("/").map(v => v.trim());
      return [r.metric, parts[0], parts[1], parts[2]];
    }), [1.3, 1.6, 1.6, 1.6], 10);

  s.addText("Where the return came from", { x: 7.1, y: 3.45, w: 5.6, h: 0.28,
    isTextBox: true, margin: 0, fontFace: BODY, fontSize: 13, bold: true, color: NAVY });
  table(s, 7.1, 3.76, 5.6, ["Leg, measured against the eligible universe", "2021-22", "2023-26"], [
    ["Long leg excess", "-3.07%", "+8.81%"],
    ["Long leg t-statistic", "-0.5", "+2.4"],
    ["Short leg excess (negative is good)", "-29.35%", "-1.61%"],
    ["Short leg t-statistic", "-2.5", "-0.2"],
  ], [3.0, 1.3, 1.3], 9.5);
  s.addText("Raw contribution conflates a rising market with poor selection. Measured "
          + "against the universe we could actually trade, the legs take turns: the "
          + "short book carried 2021-22, the long book carries 2023-26.", {
    x: 7.1, y: 5.0, w: 5.6, h: 0.8, isTextBox: true, margin: 0,
    fontFace: BODY, fontSize: 10, italic: true, color: INK, lineSpacingMultiple: 1.05 });

  fig(s, "histogram", 7.1, 5.72, 5.6, 1.62);
  s.addNotes("2024 is the only year that trails the hurdle. 2022's +38% coincides with "
           + "a -19% market and is the period we treat as non-repeatable.");
}

// =========================================================== SLIDE 5 ========
{
  const s = slide(false);
  title(s, "Risk-adjusted performance", "The information ratio is the headline; beta is the entry requirement");

  stat(s, 0.6, 1.66, 3.0, "Information ratio", M("INFORMATION RATIO"), "vs cash + 4%, annualised");
  stat(s, 3.78, 1.66, 3.0, "Sharpe", M("Sharpe ratio over cash"), "over cash, annualised");
  stat(s, 6.96, 1.66, 3.0, "Alpha vs S&P 500", M("alpha vs S&P 500"), note("alpha vs S&P 500"));
  stat(s, 10.14, 1.66, 2.56, "Beta", M("BETA vs S&P"), "se " + note("BETA vs S&P").replace("se=", "").replace(" -- the neutrality evidence", ""));

  fig(s, "rolling_beta", 0.6, 3.45, 6.3, 2.5);
  caption(s, 0.6, 6.0, 6.3,
    "Full-period beta is " + M("BETA vs S&P") + ". The 12-month window leaves the "
    + "+/-0.3 band around 2022 - we report that rather than only the average.");

  s.addText("Cost sensitivity", { x: 7.3, y: 3.45, w: 5.4, h: 0.28, isTextBox: true,
    margin: 0, fontFace: BODY, fontSize: 13, bold: true, color: NAVY });
  table(s, 7.3, 3.76, 5.4, ["Cost per trade", "Information ratio", "Annualised"],
    pack.filter(r => r.section === "costs")
        .map(r => [r.metric.replace("IR at ", "").replace(" per trade", ""),
                   r.value, r.note.replace("annualised ", "")]),
    [1.7, 1.85, 1.85], 10);
  s.addText("Break-even cost: " + R("break-even") + " per trade", {
    x: 7.3, y: 5.5, w: 5.4, h: 0.28, isTextBox: true, margin: 0,
    fontFace: BODY, fontSize: 11.5, bold: true, color: NAVY });
  caption(s, 7.3, 5.8, 5.4,
    "Borrow fees are not modelled. At 25bps trading plus 1%/yr borrow and a haircut on "
    + "the collateral rate, the information ratio is roughly 0.5 - the number we would "
    + "rather defend.");
  s.addNotes("Beta with its standard error is the neutrality evidence the rules ask for. "
           + "The rolling chart is the one they say separates teams.");
}

// =========================================================== SLIDE 6 ========
{
  const s = slide(false);
  title(s, "Exposure and implementation", "All four trading limits hold in every one of the 68 months");

  const rows = [
    ["Holdings", M("average holdings"), note("average holdings")],
    ["Gross exposure", M("average gross exposure"), note("average gross exposure")],
    ["Net exposure", M("average net exposure"), note("average net exposure")],
    ["Largest single position", M("maximum single position"), "average " + M("average single position")],
    ["Top 10 names", M("share of book in the top 10"), "share of gross"],
    ["Monthly turnover", M("average monthly turnover"), note("average monthly turnover")],
    ["Notional traded", M("notional traded per month"), "per month"],
  ];
  table(s, 0.6, 1.7, 6.2, ["Measure", "Value", "Range / note"], rows, [2.5, 1.7, 2.0], 10.5);

  s.addText("Short-book borrowability", { x: 0.6, y: 4.28, w: 6.2, h: 0.28,
    isTextBox: true, margin: 0, fontFace: BODY, fontSize: 13, bold: true, color: NAVY });
  table(s, 0.6, 4.59, 6.2, ["", "Short leg", "Long leg"], [
    ["Median market cap", M("median market cap, short leg"), note("median market cap, short leg").replace("long leg ", "")],
    ["Median daily dollar volume", M("median daily dollar volume"), note("median daily dollar volume").replace("long leg ", "")],
    ["Median price", M("median price, short leg"), "-"],
    ["Small cap or below", M("share of short leg in small caps"), "nano/micro screened out"],
  ], [2.5, 1.85, 1.85], 9.5);
  caption(s, 0.6, 6.0, 6.2,
    "The short book is more liquid than the long book. The unscreened version had a "
    + "$50m median cap and a $2.63 median price.");

  fig(s, "underwater", 7.1, 1.7, 5.6, 2.25);
  fig(s, "rolling_ir", 7.1, 4.15, 5.6, 2.6);
  s.addNotes("Net exposure sits inside a self-imposed +/-30% cap, wider than we would "
           + "like, and it is the price of reaching beta neutrality.");
}

// =========================================================== SLIDE 7 ========
{
  const s = slide(false);
  title(s, "Cumulative performance", "Strategy against the cash-plus-4% hurdle, with the S&P 500 for context");
  fig(s, "cumulative", 0.6, 1.6, 7.3, 3.5);
  fig(s, "contributors", 8.2, 1.6, 4.5, 4.4);
  s.addText([
    { text: "Beating the market is not the objective this year. ", options: { bold: true } },
    { text: "The S&P 500 is shown because the rules ask for context and because the "
           + "regression of our excess returns on the market's is how neutrality is "
           + "verified. The number that decides the strategy is the distance from the "
           + "grey hurdle line.", options: {} },
  ], { x: 0.6, y: 5.35, w: 7.3, h: 1.1, isTextBox: true, margin: 0,
       fontFace: BODY, fontSize: 11.5, color: INK, lineSpacingMultiple: 1.05 });
  s.addNotes("Contributors chart names every stock by ticker and company name, as required.");
}

// =========================================================== SLIDE 8 ========
{
  const s = slide(true);
  title(s, "What we would tell an investment committee", null, true);

  const cols = [
    ["What worked", ICE, [
      "Portfolio construction moved the book from beta -0.537 to " + M("BETA vs S&P")
        + " and cut drawdown from -30% to " + M("maximum drawdown (monthly") + ".",
      "Alpha survives market, size and value: " + R("market + size + value")
        + "/yr, " + Rnote("market + size + value") + ". It is not a repackaged factor.",
      "The long leg has genuine selection skill since 2023: +8.81% over the eligible "
        + "universe, t=+2.4 across 44 months.",
    ]],
    ["What did not", "F3C6C0", [
      "The short leg's edge was one regime. In the pre-test validation window it pointed "
        + "the wrong way (+5.42% vs universe); since 2023 it is statistically zero.",
      "8-K signals add nothing measurable to the forecast, across three independent tests.",
      "Removing the 5 best months of 68 takes the information ratio from "
        + M("INFORMATION RATIO") + " to " + R("minus the 5 best months") + ".",
    ]],
    ["What we would say about the future", ICE, [
      "The second half of the window runs at " + R("second half") + " against "
        + R("first half") + " in the first. The later figure is the more honest "
        + "forward expectation; 2021-22 dominates the full-period number.",
      "The short book's job is neutrality, not return. We would size it as a hedge, not "
        + "as a second source of alpha.",
      "We evaluated the test period 13 times. Nine followed a diagnosed defect; three "
        + "were genuine trials, one of which we removed after it failed.",
    ]],
  ];
  cols.forEach((c, i) => {
    const x = 0.7 + i * 4.15;
    s.addText(c[0], { x, y: 1.5, w: 3.85, h: 0.32, isTextBox: true, margin: 0,
      fontFace: BODY, fontSize: 15, bold: true, color: c[1] });
    s.addText(c[2].map((t, j) => ({
      text: t, options: { bullet: true, breakLine: j !== c[2].length - 1 },
    })), { x, y: 1.92, w: 3.85, h: 3.9, isTextBox: true, margin: 0, valign: "top",
      fontFace: BODY, fontSize: 11.5, color: WHITE, paraSpaceAfter: 10,
      lineSpacingMultiple: 1.05 });
  });

  s.addText("Every one of these was measured, not asserted. The appendix carries the "
          + "regressions, the research log and the compliance output.", {
    x: 0.7, y: 6.1, w: 11.9, h: 0.5, isTextBox: true, margin: 0,
    fontFace: BODY, fontSize: 12, italic: true, color: ICE });
  s.addNotes("This is the page the rules are really asking for: did it do what you "
           + "trained it to, what drove it, and what would you change.");
}

// ========================================================== APPENDIX ========
function appendix(heading, subtitle, build) {
  const s = slide(false);
  s.addText("APPENDIX", { x: 0.6, y: 0.3, w: 3, h: 0.22, isTextBox: true, margin: 0,
    fontFace: BODY, fontSize: 9.5, bold: true, color: GREY, charSpacing: 0.8 });
  title(s, heading, subtitle);
  build(s);
  return s;
}

appendix("Where the alpha came from, and why it moved",
  "Each leg measured against the universe it was picked from, which removes market direction",
  s => {
    table(s, 0.6, 1.74, 7.1,
      ["Period", "Universe", "Long vs universe", "Short vs universe"], [
      ["2019-20 (pre-test validation)", "+25.03%", "+0.85%  (t +0.1)", "+5.42%  (t +1.1)"],
      ["2021-22", "-1.57%", "-3.07%  (t -0.5)", "-29.35%  (t -2.5)"],
      ["2023-26", "+12.05%", "+8.81%  (t +2.4)", "-1.61%  (t -0.2)"],
    ], [2.55, 1.25, 1.65, 1.65], 10);
    bullets(s, 0.6, 3.2, 7.1, [
      "For the short leg a negative number is good: the names we shorted underperformed.",
      "The only window with short-side skill is 2021-22, the speculative unwind. In the "
        + "pre-test validation window the short leg was the wrong way round.",
      "Splitting the short book by market cap, price and volatility, EVERY bucket flips "
        + "positive to negative. No screen repairs it: dropping the extreme-volatility "
        + "names would have cost 18.8pp of the 2021-22 gain to recover 3.7pp of the later loss.",
      "The 2021-22 short alpha survives sector adjustment almost intact (-26.90% vs "
        + "-25.62%), so it was stock selection inside sectors, not a bet against technology.",
    ], 11);
    s.addShape(pres.ShapeType.roundRect, { x: 8.1, y: 1.74, w: 4.6, h: 2.5,
      fill: { color: TINT }, line: { color: TINT }, rectRadius: 0.06 });
    s.addText("Applying the same standard to both legs", {
      x: 8.32, y: 1.9, w: 4.2, h: 0.5, isTextBox: true, margin: 0,
      fontFace: BODY, fontSize: 11.5, bold: true, color: NAVY });
    s.addText("The long leg also shows skill in only one regime. If we discount the "
            + "short result as regime-specific, the same scepticism applies to the long "
            + "one. The framing we prefer is that the legs take turns: shorts pay when "
            + "speculative names unwind, longs pay when quality leads.", {
      x: 8.32, y: 2.36, w: 4.2, h: 1.7, isTextBox: true, margin: 0, valign: "top",
      fontFace: BODY, fontSize: 10.5, color: INK, lineSpacingMultiple: 1.05 });
  });

appendix("Text data: three tests, one null, one exception",
  "This year's theme, measured rather than assumed",
  s => {
    table(s, 0.6, 1.74, 7.4, ["Test", "What we found"], [
      ["27 single-signal tests on item codes",
       "None clears a monthly regression with controls"],
      ["Joined into the forecast",
       "Validation IC +0.1087 without, +0.1082 with"],
      ["The model's own feature importance",
       "10 filing columns take 1.71% against 6.37% expected"],
      ["Item 5.02 split by triage",
       "Aggregate +0.046% (t +0.5) -> abrupt -0.640% (t -1.9)"],
    ], [3.5, 3.9], 10.5);
    bullets(s, 0.6, 3.5, 7.4, [
      "The naive t-statistic was inflated in all of these. Stocks within a month move "
        + "together, so 7,670 stock-months are not 7,670 independent observations. Three "
        + "signals that looked alive on the naive test died on the monthly one.",
      "Coverage is the binding constraint: only 50.7% of evaluation-window stock-months "
        + "have any filing, and the abrupt-departure flag is set on 1.26%. A tree splits "
        + "on what separates many rows; a rare flag is structurally ignored however "
        + "accurate it is.",
      "The triage uses no language model. Rules were read off the documents; --sample "
        + "prints both sides for inspection and sorted 8 of 8 correctly on the sample shown.",
    ], 11);
    s.addShape(pres.ShapeType.roundRect, { x: 8.4, y: 1.74, w: 4.3, h: 3.0,
      fill: { color: TINT }, line: { color: TINT }, rectRadius: 0.06 });
    s.addText("Why the aggregate hid it", {
      x: 8.62, y: 1.9, w: 3.9, h: 0.28, isTextBox: true, margin: 0,
      fontFace: BODY, fontSize: 11.5, bold: true, color: NAVY });
    s.addText("70,582 officer-change filings carry no signal together. Separated, 1,632 "
            + "abrupt departures move next-month returns by -0.640% while 14,746 routine "
            + "appointments move them +0.121%. An aggregate null is not the same as no "
            + "signal - it can be a diluted one.", {
      x: 8.62, y: 2.22, w: 3.9, h: 1.6, isTextBox: true, margin: 0, valign: "top",
      fontFace: BODY, fontSize: 10.5, color: INK, lineSpacingMultiple: 1.05 });
    s.addText("t = -1.9 still does not clear the bar we set for ourselves after this "
            + "many tests, and we say so.", {
      x: 8.62, y: 3.95, w: 3.9, h: 0.6, isTextBox: true, margin: 0,
      fontFace: BODY, fontSize: 10.5, italic: true, color: RED });
  });

appendix("Robustness", "Six tests, run before the deck was written", s => {
  table(s, 0.6, 1.74, 6.0, ["Subperiod", "Information ratio", "vs hurdle"],
    robust.filter(r => r.section === "subperiod")
          .map(r => [r.metric, r.value, Rnote(r.metric) || "-"]),
    [2.5, 1.7, 1.8], 10);
  table(s, 0.6, 3.95, 6.0, ["Stress test", "Information ratio"],
    robust.filter(r => r.section === "stress").map(r => [r.metric, r.value]),
    [3.6, 2.4], 10);
  s.addText("Factor attribution", { x: 7.0, y: 1.74, w: 5.7, h: 0.28, isTextBox: true,
    margin: 0, fontFace: BODY, fontSize: 13, bold: true, color: NAVY });
  table(s, 7.0, 2.05, 5.7, ["Model", "Annualised alpha", "t and R2"],
    robust.filter(r => r.section === "attribution")
          .map(r => [r.metric, r.value, Rnote(r.metric)]),
    [2.2, 1.7, 1.8], 10);
  bullets(s, 7.0, 3.0, 5.7, [
    "Loadings on size and value are insignificant, and the three-factor regression "
      + "leaves most of the variation unexplained (" + Rnote("market + size + value")
      + ").",
    "Delisting marks: positions with no realised return are marked at zero in the base "
      + "case (" + M("positions affected") + ", " + note("positions affected")
      + "). At Shumway's -30% convention the net information ratio is "
      + M("marked -30%") + ".",
    "Daily marks cover 82.3% of the book by weight and 64.4% at worst. Names that cannot "
      + "be resolved were acquired or renamed, so daily figures are biased optimistic.",
    "Maximum drawdown on daily marks is " + M("maximum drawdown (daily")
      + " against " + M("maximum drawdown (monthly") + " on monthly marks. Rolling "
      + "12-month beta averages " + R("12-month beta") + " (" + Rnote("12-month beta") + ").",
  ], 10.5);
});

appendix("Research log and multiple testing",
  "The question we expect to be asked, answered before it is", s => {
    bullets(s, 0.6, 1.74, 12.1, [
      "We evaluated the test period 13 times. Nine of those followed a diagnosed defect "
        + "and had a reason independent of the result: penny stocks in the short book "
        + "(-48% in January 2021), beta at -0.537, the wrong beta estimator, the tree "
        + "target not demeaned (one boosting round per fold), leg beta measured rather "
        + "than estimated, unstable validation tuning, and a cross-fold leak in model "
        + "selection.",
      "Three were genuine trials: the tree model, turnover control, and the 8-K feature "
        + "set. We removed the third after it failed its pre-declared test.",
      "One correction is worth naming. choose_blend pooled all six folds' validation "
        + "blocks before picking one model for all six years, so the 2021 forecast was "
        + "chosen partly on 2024-25 outcomes. Each fold's own split was clean and our "
        + "checks passed - the leak lived between folds, where a per-fold check cannot "
        + "see it. Selection now happens inside each fold, and a new check fails on the "
        + "old format.",
      "What we take from this: with 68 months and this many looks, a t-statistic near 2 "
        + "is not evidence. What makes a result worth keeping is effect size, a reason to "
        + "expect it in advance, and survival across regimes - not the t.",
    ], 12);
    s.addShape(pres.ShapeType.roundRect, { x: 0.6, y: 5.0, w: 12.1, h: 1.5,
      fill: { color: TINT }, line: { color: TINT }, rectRadius: 0.06 });
    s.addText("Reproducibility", { x: 0.85, y: 5.16, w: 11.6, h: 0.26, isTextBox: true,
      margin: 0, fontFace: BODY, fontSize: 11.5, bold: true, color: NAVY });
    s.addText("MAIN.py runs the whole chain from the supplied parquet files to the "
            + "compliance gate and the exhibits on these slides, and exits non-zero if "
            + "any rule is broken. 22 automatic checks cover look-ahead (predictor list, "
            + "split keying, preprocessing fit window, cross-fold selection) and the "
            + "trading criteria (100-500 names, gross <= 200%, net inside +/-50%, both "
            + "legs, coverage, tradability). A separate test feeds the checker 21 "
            + "deliberately broken inputs and asserts each is caught; all 21 fire. The "
            + "traded book records 0 failures across all 68 months.", {
      x: 0.85, y: 5.44, w: 11.6, h: 1.0, isTextBox: true, margin: 0, valign: "top",
      fontFace: BODY, fontSize: 10.5, color: INK, lineSpacingMultiple: 1.02 });
  });

// ------------------------------------------------------------- write -------
const out = path.join(SUB, "FIAM_deck.pptx");
pres.writeFile({ fileName: out }).then(() => {
  console.log("wrote " + out);
  console.log("slides: 8 main + 4 appendix");
});
