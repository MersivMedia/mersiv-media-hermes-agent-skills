# ROI Sizing Patterns

Reusable formulas for turning disclosed financials into defensible opportunity
sizes, plus the rules for presenting them without losing the room.

## Rule zero

**Derive from disclosed figures. Show the arithmetic. Tag every assumption.**

An unshown number is unattackable and therefore untrusted. A CFO who cannot
check your maths will discount it entirely — and in most rooms the CFO is the
person whose approval you actually need.

## Establishing the baseline

Pull these from the latest earnings release or 10-K and put them in one table
at the top of any sizing section:

| Input | Typical source |
|---|---|
| Revenue | Earnings release headline |
| Units / transactions | Operational data section |
| Average unit price | Disclosed or revenue ÷ units |
| Gross margin % | Disclosed, use the **adjusted** figure |
| SG&A % of revenue | Disclosed, use **adjusted** |
| Gross profit per unit | Derived: ASP × margin % |
| Direct cost base | Derived: revenue × (1 − margin %) |

**Always prefer adjusted figures**, and say you are. One-time charges (M&A
compensation, impairments) distort reported numbers badly and using them makes
you look careless.

**Annualise carefully.** One soft quarter × 4 overstates the decline if the
business is seasonal. Say which method you used.

## Pattern 1 — Attach rate / cross-sell uplift

For any add-on, option, upgrade or attached service.

```
Attach revenue     = attach_rate_value_per_unit × units
Attach gross profit= attach_revenue × attach_margin
Uplift value       = attach_gross_profit × uplift_%
```

Attach margin is usually **higher** than blended margin — say so, it
strengthens the case. Realistic uplift from better targeting: **3-5%**.
Anything above 10% needs a specific mechanism you can name.

## Pattern 2 — Conversion / funnel

The seductive one. Almost always your biggest number and your weakest claim.

```
Incremental units = locations × Δ(rate per location per period) × periods
Value             = incremental_units × gross_profit_per_unit
```

**Discount this heavily and say why.** Demand metrics move with macro
conditions — interest rates, consumer confidence, seasonality. A buyer will
attribute any change to those, correctly. Present it as a **controlled
experiment with a defined cost**, never as promised value.

## Pattern 3 — Direct cost reduction

```
Addressable base = direct_cost × influenceable_%   [ASSUMPTION, state it]
Value            = addressable_base × capture_%
```

`influenceable_%` is rarely above 60% — much of direct cost is contractually
or physically fixed. Realistic first-year capture on a large base: **0.3-0.75%**.
Small percentages on big bases produce large numbers; resist rounding up.

## Pattern 4 — Overhead / G&A efficiency

```
Addressable G&A = total_SG&A × addressable_%   (~40% is a common default)
Value           = addressable_G&A × efficiency_%
```

Realistic: **3-7%**.

**The framing rule is absolute.** If the company holds workplace awards
(Fortune Best Companies, Great Place To Work), culture is a public asset.
Never present this as headcount reduction. Present it as *the same team
absorbing growth without adding people* — which is usually a commitment their
CFO has already made publicly.

## Pattern 5 — Cycle time / working capital

```
Carrying cost per unit per day = unit_WIP_value × annual_rate ÷ 365
Value                          = days_saved × units × carrying_cost_per_day
```

The direct number is modest. The larger benefit is inventory turn and capital
efficiency — mention it, but don't try to price it precisely without their
internal data.

## Pattern 6 — Process automation (document / transaction volume)

```
Transaction cost base = transactions × industry_cost_per_transaction
Value                 = cost_base × reduction_%
```

Use a **published industry benchmark** for per-transaction cost and cite it.
Realistic reduction: **15-25%**.

## Presenting the portfolio

Table with **conservative and optimistic columns**, a confidence level, and a
named internal sponsor per line. Then three things:

**1. Express as margin, not just dollars.** "$18-39M annually, roughly 60-140
basis points of pretax margin" is checkable against their own P&L. A raw
dollar total invites scepticism.

**2. Give a defensible subtotal.** Explicitly exclude your weakest-attribution
line:

> "Excluding the demand-side play, which we would test rather than promise,
> the defensible portfolio is $X-Y annually."

**3. Sanity-check the total.** If the sum exceeds ~30% of the company's pretax
income, it will read as fantasy regardless of the arithmetic. Lead with the
conservative figure and let them ask about the upside.

## Payback

```
Payback months = engagement_cost ÷ (annual_value ÷ 12)
```

Common private-company threshold: **12-24 months**, preference under 18.
Public companies under quarterly pressure often want faster; recently-acquired
companies with an efficiency mandate sometimes tolerate longer.

**Ask where the cost lands.** Operating expense, cost of sales, or capitalised
software materially changes the ratios a CFO is defending — and can decide
whether the deal happens at all.

## Worked example

Homebuilder, ~4,200 deliveries/yr, $676K ASP, 20.8% adjusted gross margin.

```
Revenue                   = 4,200 × $676,000        = $2.84B
Gross profit per home     = $676,000 × 20.8%        = $140,600
Options revenue (~10% ASP)= $65,000 × 4,200         = $273M
Options margin (~35%)     [ASSUMPTION]
3% attach uplift          = $273M × 3%              = $8.2M revenue
                          = $8.2M × 35%             = $2.9M gross profit
```

Conservative $2.5M, optimistic $4.5M, confidence MEDIUM-HIGH — because two
independent sources (a CMO earnings-call remark and a VP job description)
named the same problem.

## Honesty checklist

- [ ] Every figure traces to a disclosed number or a tagged `[ASSUMPTION]`
- [ ] Adjusted figures used, and labelled as adjusted
- [ ] Conservative and optimistic ends given, never a point estimate
- [ ] The weakest line is explicitly flagged as such
- [ ] A defensible subtotal excluding it is provided
- [ ] Total sanity-checked against pretax income
- [ ] Payback computed against the buyer's likely threshold
- [ ] Accounting treatment raised as an open question
