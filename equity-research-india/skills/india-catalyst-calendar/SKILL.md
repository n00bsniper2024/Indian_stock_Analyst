---
name: india-catalyst-calendar
description: Build a forward calendar of Indian-market catalysts for a watchlist — results dates, board meetings, dividends/record dates, AGMs, RBI MPC, Union Budget, GST Council, monthly macro and industry data, F&O expiries, index rebalancing — with expected impact. Use for "what's coming up for my stocks", "results calendar", "events this week Indian market".
---

# India catalyst calendar

Adapted from Anthropic's `catalyst-calendar` skill with an Indian event set.
Read `${CLAUDE_PLUGIN_ROOT}/references/india-research-standards.md` first.

## Event types to collect (verify every date at the source — they move)
**Company:** board-meeting intimations for results (NSE/BSE "board meetings" — usually 2–7 days' notice), results
(Q1–Q3 within 45 days, Q4 within 60 days), concalls, dividends/record & ex-dates, bonus/split, buybacks, QIP/OFS,
AGM/EGM/postal ballots, promoter lock-in expiries, credit-rating reviews, plant commissioning, regulatory approvals
(USFDA inspections for pharma, RBI licences, spectrum auctions), large order announcements.
**Market structure:** monthly F&O expiry, F&O ban list, Nifty/Sensex semi-annual rebalancing (effective end-March and
end-September; announced ~4 weeks earlier), MSCI/FTSE quarterly reviews, ASM/GSM list changes.
**Policy & macro:** RBI MPC (six meetings a year), Union Budget (1 February), GST Council meetings, CPI/WPI (monthly,
~12th/14th), IIP, GDP (quarterly, end of month after quarter), PMI (1st–3rd business day), trade data, IMD monsoon forecasts
(April, end-May) and progress (June–September), US Fed decisions, crude oil and INR moves.
**Industry data:** SIAM/OEM monthly auto sales (1st of month), cement and steel volumes, power demand (CEA/Grid-India),
GST collections, AMFI monthly flows, SIP data, credit growth (RBI fortnightly).

## Workflow
1. Watchlist + horizon (default: next 30 days).
2. For each stock run `python -m isa.cli analyze <SYMBOL> --no-peers` for price context (nearest support/resistance, ATR)
   — useful for planning around binary events.
3. Gather dates with citations; mark unconfirmed dates as "expected (based on last year)".
4. Rate impact H/M/L with a one-line reason and the metric to watch (e.g. "Q2 margin vs 18.2% last quarter").

## Output
| Date | Event | Stock/Sector | Type | Impact | What to watch | Source |
Weekly preview paragraph + "binary-event risk" list (results, court/regulatory rulings) with ATR-based expected move.
Optionally an `.ics` file or spreadsheet (via the `xlsx` skill).
