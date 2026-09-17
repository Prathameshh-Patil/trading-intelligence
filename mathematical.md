I’ll turn this into a mathematically explicit, testable specification rather than a
discretionary checklist. I’m first checking the stated prop-firm constraints and the
instrument-unit assumptions, then I’ll define the feature calculations, regime model,
entry/exit rules, risk engine, and validation protocol.## Strategy Specification:
GC/XAUUSD Magnitude Expansion
This should be treated as a research and execution framework, not a guaranteed
predictive system. The correct objective is:
Estimate whether the conditional distribution of the next 30-90 minute absolute move
has sufficient upper-tail magnitude to justify a trade.
The model should not attempt to forecast an exact price target. It should estimate:
[ M_{t,h} = \left|P_{t+h}-P_t\right| ]
where (h \in {30,60,90}) minutes and (M) is measured in GC ticks.
A trade is permitted only when the forecast distribution satisfies:
[ Q_{0.60}(M_{t,60}) > 150 \text{ ticks} ]
or, more conservatively:
[ P(M_{t,60} \geq 150) \geq 0.60 ]
The first condition is the minimum volatility filter. The second is the actual trade-quality
filter.
A 100-tick GC move equals $10.00 per ounce and $1,000 per standard GC contract
because GC is $10 per tick. XAUUSD pip conventions are broker-dependent, so the
strategy should use dollar and price-distance normalization rather than assuming that
every broker defines a pip identically.
The stated prop-firm rules should be implemented as an internal risk overlay, not
assumed to be identical across firms. Current published rules differ materially: Topstep
uses program-specific maximum-loss, consistency, position-size, and optional daily-loss
rules; FTMO uses account-specific maximum-loss and best-day rules; Apex permits
some news trading subject to restrictions; and Take Profit Trader’s current published
policy does not match the stated universal consistency assumptions. (help.topstep.com)
1. Data and Normalization
Instruments
Use:
●
●
●
●
Primary execution instrument: front-month CME GC contract
Secondary execution instrument: MGC, if required for risk granularity
Reference instrument: XAUUSD
Cross-asset features:
●
DXY
●
US 10Y yield
●
ES
●
NQ
●
VIX
For GC:
[ \text{Dollar P/L} = \text{ticks} \times $10 \times \text{contracts} ]
For MGC:
[ \text{Dollar P/L} = \text{ticks} \times $1 \times \text{contracts} ]
All continuous-contract features must be calculated using a back-adjusted series, while
execution and order-book features must use the actual front-month contract.
Rollover weeks must be labeled explicitly:
[ R_t = \begin{cases} 1, & \text{if within 5 trading days of defined rollover date}\ 0, &
\text{otherwise} \end{cases} ]
Do not silently mix volume, price, and order-book data across contracts.
Required timestamps
Normalize all data to UTC internally and derive:
●
●
●
●
New York time
London time
CME session date
RTH session date
The strategy's active windows are:
[ 08{:}00-11{:}30 \text{ New York time} ]
and
[ 13{:}30-15{:}30 \text{ New York time} ]
No entries are allowed outside those windows.
2. Volatility Regime Model
Yang-Zhang realized volatility
For each 5-minute bar:
[ r_o = \ln\left(\frac{O_t}{C_{t-1}}\right) ]
[ r_c = \ln\left(\frac{C_t}{O_t}\right) ]
[ r_{rs} = \ln\left(\frac{H_t}{O_t}\right) \ln\left(\frac{H_t}{C_t}\right) +
\ln\left(\frac{L_t}{O_t}\right) \ln\left(\frac{L_t}{C_t}\right) ]
With (n) bars:
[ \sigma^2
_{YZ}
\sigma_o^2 + k\sigma_c^2 + (1-k)\sigma_{rs}^2 ]
where:
[ k = \frac{0.34}{1.34+\frac{n+1}{n-1}} ]
Use rolling windows of:
●
●
●
12 bars: 60-minute local volatility
48 bars: 4-hour volatility
288 bars: one trading day
Annualization is unnecessary for the direct range estimate. Convert volatility to
expected 60-minute ticks:
[
YZ}
\widehat{R}_{60}^{
\frac{P_t \cdot \sigma_{60}^{YZ}}{\text{GC tick size}} ]
GARCH(1,1)
Fit:
[ \epsilon_t = \sigma_t z_t ]
[ \sigma_{t+1}^2 = \omega+\alpha\epsilon_t^2+\beta\sigma_t^2 ]
Use Student-t innovations rather than Gaussian innovations because GC returns have
fat tails.
The forecast for the next 60-minute variance is:
[
\widehat{\sigma}_{
60,GARCH}^2
\bar{\sigma}^2+ (\alpha+\beta)^{m} \left(\sigma_t^2-\bar{\sigma}^2\right) ]
where (m) is the number of 5-minute intervals in the forecast horizon.
Combined expected range
Use a volatility ensemble:
[ \widehat{R}_{60}
w_{YZ}\widehat{R}{60}^{YZ} + w_G\widehat{R}{60}^{GARCH} ]
with weights determined in walk-forward training. Initial weights:
[ w_{YZ}=0.5,\qquad w_G=0.5 ]
Trade filter:
[ \widehat{R}_{60} > 150 \text{ ticks} ]
Additional quality filter:
[ \frac{\widehat{R}{60}}{R{60,\text{median}}} > 1.20 ]
This prevents trading merely because current volatility is high relative to an already
elevated baseline.
3. Volume-Clock Features
Construct bars every 1,000 GC contracts rather than at fixed time intervals.
For volume bar (j):
[ OFI_j = \frac{B_j-A_j}{B_j+A_j+\epsilon} ]
where:
●
●
●
(B_j): bid-side executed or displayed volume
(A_j): ask-side executed or displayed volume
(\epsilon): small numerical stabilizer
For the 10-second rolling feature:
[ OFI
_{10s,t}
\frac{ \sum_{i=t-9}^{t}B_i-\sum_{i=t-9}^{t}A_i }{
\sum_{i=t-9}^{t}B_i+\sum_{i=t-9}^{t}A_i+\epsilon } ]
Calculate a session- and time-of-day-normalized z-score:
[ OFI_z = \frac{OFI_{10s,t}-\mu_{OFI,\tau}} {\sigma_{OFI,\tau}+\epsilon} ]
where (\tau) is the time-of-day bucket.
Use separate distributions for:
●
●
●
●
●
London-New York overlap
US RTH open
Midday
Afternoon
Rollover-week sessions
A raw OFI of 0.5 at 08:30 should not be compared with a raw OFI of 0.5 at 14:45
without normalization.
4. Delta and Cumulative Delta
Define aggressive delta:
[ \Delta_t = V^{ask}_t - V^{bid}_t ]
Cumulative delta:
[ CVD_t = \sum_{i=1}^{t}\Delta_i ]
Use slope rather than level:
[ \beta
_{CVD,t}
\frac{\operatorname{Cov}(s,CVD)} {\operatorname{Var}(s)} ]
where (s) is the sequence of recent volume bars.
Normalize:
[ CVD_z = \frac{\beta_{CVD,t}-\mu_{\beta,\tau}} {\sigma_{\beta,\tau}+\epsilon} ]
For a long setup, require:
[ CVD_z > 1.0 ]
For a short setup:
[ CVD_z < -1.0 ]
Delta divergence
For long accumulation:
[ \Delta P_{20} \leq 0.25 \cdot ATR_{20} ]
and:
[ CVD_{20} \geq Q_{0.70}(CVD_{20}) ]
Interpretation: aggressive buying is occurring without equivalent upward price
displacement, suggesting passive offer absorption followed by potential release.
For short distribution, invert the conditions.
5. Hawkes Trade-Arrival Model
Model aggressive trade arrivals as a marked Hawkes process:
[ \lambda
t
_
\mu + \sum_{t_i<t} \alpha m_i e^{-\beta(t-t_i)} ]
where:
●
●
●
●
●
(\lambda_t): current trade-arrival intensity
(\mu): baseline intensity
(m_i): trade-size mark
(\alpha): excitation coefficient
(\beta): decay coefficient
Estimate separate processes for:
●
●
●
●
Buy-initiated trades
Sell-initiated trades
Large trades
Small trades
Define branching ratio:
[ n = \frac{\alpha}{\beta} ]
Interpretation:
●
●
●
(n < 0.5): mostly independent flow
(0.5 \leq n < 1): clustered flow
(n \geq 1): unstable or highly self-exciting flow
Use Hawkes features:
[ H_{\text{buy}} = \lambda_{\text{buy}}-\lambda_{\text{sell}} ]
[ H_{\text{cluster}} = \lambda_{\text{buy}}+\lambda_{\text{sell}} ]
Absorption versus initiation
A practical classification:
Absorption:
[ |r_{10s}| < Q_{0.35}(|r_{10s}|) ]
[ |\Delta_{10s}| > Q_{0.70}(|\Delta_{10s}|) ]
[ \lambda_t > Q_{0.70}(\lambda) ]
Initiation:
[ |r_{10s}| > Q_{0.70}(|r_{10s}|) ]
[
\operatorname{sig
n}(r
_{10s})
\operatorname{sign}(\Delta_{10s}) ]
[ \lambda_t > Q_{0.75}(\lambda) ]
For a long trade, the preferred sequence is:
1. Buy-side absorption near a downside liquidity level.
2. CVD remains positive or recovers.
3. Buy-side Hawkes intensity increases.
4. Price breaks the local balance range.
5. OFI remains positive after the break.
This distinguishes trapped aggressive sellers from genuine continuation buying.
6. Hurst and Fractional-Brownian
Component
Estimate the Hurst exponent using at least two methods:
●
●
Detrended fluctuation analysis
Variance-time regression
For variance-time estimation:
[ \operatorname{Var}(X_{t+\tau}-X_t) \propto \tau^{2H} ]
Therefore:
[ H = \frac{1}{2} \frac{\partial \log \operatorname{Var}(\Delta X_\tau)} {\partial \log \tau} ]
Use several scales:
[ \tau \in {10s,30s,60s,5m,15m,30m} ]
Do not trade from one noisy Hurst estimate. Require:
[ H_{15m} > 0.55 ]
and preferably:
[ H_{5m} > 0.50 ]
For the high-conviction expansion setup:
[ H_{15m} > 0.58 ]
Interpretation:
●
●
●
●
(H<0.50): anti-persistent, mean-reverting
(0.50 \leq H \leq 0.55): neutral
(H>0.55): persistent
(H>0.58): expansion-compatible, subject to confirmation
The fractional Brownian motion component should not be used to generate a direct
price forecast. It should modify the expected magnitude:
\widehat{M}_{FBM
[
}
\sigma_{60} \left(\frac{T}{T_0}\right)^H z_q ]
where (z_q) is a selected quantile multiplier. The output is an expected movement
scale, not a target price.
7. Three-State Markov Regime Model
Define the latent state:
[ S_t \in {C,B,E} ]
where:
●
●
(C): Chop
(B): Imbalance Build
●
(E): Expansion
Observation vector:
[ X_t = [ \widehat{R}_{60}, OFI_z, CVD_z, H, \lambda_t, \text{spread}, \text{depth
imbalance}, \text{range compression} ] ]
Fit a Gaussian or Student-t hidden Markov model with transition matrix:
[ P = \begin{bmatrix} p_{CC} & p_{CB} & p_{CE}\ p_{BC} & p_{BB} & p_{BE}\ p_{EC} &
p_{EB} & p_{EE} \end{bmatrix} ]
The core trade transition is:
[ P(S_{t+1}=E \mid S_t=B, X_t) > 0.60 ]
Do not enter merely because the model identifies the Expansion state. The preferred
event is:
[ P(B_t) > 0.60 ]
followed by:
[ P(E_{t+1}) > 0.60 ]
This avoids entering after most of the expansion has already occurred.
8. Expansion Probability Model
The probability statement should be implemented as a calibrated classifier, not as a
literal unverified formula.
Long-side feature vector:
[ Z_L = [ OFI_z, D_{\text{div}}, CVD_z, H, P(B_t), P(E_{t+1}), H_{\text{buy}},
\widehat{R}{60}, S{\text{sweep}}, S_{\text{reclaim}} ] ]
Use logistic calibration:
[ p_E = \sigma\left( \theta_0+ \theta_1 OFI_z+ \theta_2 D_{\text{div}}+ \theta_3 CVD_z+
\theta_4 H+ \theta_5 P(E_{t+1})+ \theta_6 H_{\text{buy}}+ \theta_7 S_{\text{sweep}}
\right) ]
where:
[ \sigma(x)=\frac{1}{1+e^{-x}} ]
Minimum trade threshold:
[ p_E \geq 0.62 ]
High-quality threshold:
[ p_E \geq 0.68 ]
The threshold must be selected using out-of-sample calibration. A value such as 0.62 is
only an initial research threshold.
9. Entry Logic
Long setup
All conditions below must be true:
1. Active session window.
2. No high-impact news lockout.
3. (\widehat{R}_{60}>150) ticks.
4. HMM state is Build or transition probability to Expansion is elevated.
5. (P(B_t)>0.60).
6. (P(E_{t+1})>0.60).
7. (H_{15m}>0.58).
8. (CVD_z>1.0).
9. Price is flat or compressed while CVD rises.
10. (OFI_z>2.5) for three consecutive 10-second observations.
11. A prior Asian high or low is swept.
12. The sweep is reclaimed within a maximum of 30 seconds.
13. The reclaim occurs near a prior-day LVN or HVN rejection zone.
14. Hawkes intensity confirms clustered initiation.
15. Calibrated (p_E\geq0.62).
16. The stop distance produces acceptable position sizing.
Sweep definition
For an Asian-low sweep:
[ L_t < L_{\text{Asian}} ]
and reclaim:
[ C_t > L_{\text{Asian}} + \delta ]
within (N) seconds, where:
[ \delta = \max(2\text{ ticks},0.05 \cdot ATR_{10s}) ]
The sweep must not be accepted if price remains below the level for more than 30
seconds. That is more likely acceptance than rejection.
Limit entry
Let:
●
●
●
(P_s): sweep extreme
(P_r): reclaim level
(W=P_r-P_s): reclaim wick size
Long limit:
[ P_{\text{entry}}=P_s+0.50W ]
The order expires after:
[ T_{\text{expiry}}=20 \text{ seconds} ]
Cancel the order if:
●
●
●
●
●
OFI falls below (+1.0)
CVD slope reverses
price closes below the sweep extreme
Hawkes buy intensity falls below its 50th percentile
the estimated expansion probability falls below 0.55
Never convert an unfilled limit order into a market order.
10. Stop and Target
The strategy should use a structural stop, subject to a hard maximum.
For long:
[ P
_{\text{stop}}
P_s
\max(4\text{ ticks},0.10\cdot ATR_{10s}) ]
The total risk distance is:
[ D=P_{\text{entry}}-P_{\text{stop}} ]
Require:
[ 20 \leq D \leq 50 \text{ ticks} ]
If (D>50), reject the trade. Do not widen the stop.
Target selection:
[ R = \max(2.5D,;100\text{ ticks}) ]
with hard target cap:
[ R \leq 150 \text{ ticks} ]
A practical asymmetric exit:
●
●
●
●
Take 50% off at (2.5R) only if the intended notation is risk multiples.
Otherwise use a fixed 100-150 tick target.
Move stop to breakeven only after price reaches (1.5D).
Trail the remaining position using a 10-second or 1-minute volatility stop.
Because a fixed 100-150 tick target can create an unusually large nominal R multiple
when the stop is only 20-30 ticks, the backtest must distinguish:
[ \text{Target distance in ticks} ]
from:
[ \text{Risk-reward multiple} ]
The specification should not claim both “100-150 tick target” and “2.5R-4R target”
unless the stop-distance range makes them mathematically compatible.
11. Position Sizing
Let:
●
●
●
●
●
●
(A_t): current account equity
(r): risk fraction
(D): stop distance in ticks
(V): dollar value per tick
(C): contract count
(F): estimated fees and slippage
Then:
[ C
\left\lfloor \frac{A_t r} {D V+F} \right\rfloor ]
For GC:
[ V=10 ]
For MGC:
[ V=1 ]
Use:
[ r = \begin{cases} 0.004, & \text{normal conditions}\ 0.005, & \text{strong conditions}\
0.007, & \text{only after demonstrated robustness} \end{cases} ]
The strategy should default to 0.4%, not 0.7%.
Daily internal loss limit:
[ DLL_{\text{internal}}=\min(1100,;0.75\times DLL_{\text{firm}}) ]
The stated $1,100 must not be assumed to be compatible with every account size. For
example, current Topstep published account parameters vary by account size and
program, and FTMO’s limits are percentage- and account-specific. (ftmo.com)
Stop trading when any of these occurs:
[ \text{Realized P/L}+\text{Unrealized P/L} \leq -DLL_{\text{internal}} ]
[ \text{Losses today} \geq 2 ]
[ \text{Trades today} \geq 2 ]
[ \text{Daily risk consumed} \geq 0.75 \times DLL_{\text{internal}} ]
Only one position may exist at a time.
12. News Lockout
Implement a hard event calendar lock:
[ \text{No new orders during }[t_{\text{news}}-2m,;t_{\text{news}}+2m] ]
For risk control, use a wider internal lock:
[ [t_{\text{news}}-5m,;t_{\text{news}}+5m] ]
Flattening before news should be determined by the selected prop firm's rules and the
strategy's own risk policy. News rules are not uniform across firms: Apex's published
policy permits ordinary system trading during news but prohibits news strategies
intended to exploit announcements, while other firms impose different limitations.
(apextraderfunding.com)
The safest common-denominator implementation is:
●
●
●
●
No new entries from 5 minutes before high-impact news until 5 minutes
afterward.
Cancel all pending orders before the lockout.
Do not hold a position through the event unless explicitly permitted by the
account's current rules.
Treat FOMC, CPI, NFP, PCE, Fed decisions, and major employment releases as
high impact.
13. Trade Score
Use a deterministic score to prevent borderline trades:
[ Score = w_1 S_{\text{vol}} +w_2 S_{\text{OFI}} +w_3 S_{\text{CVD}} +w_4
S_{\text{Hurst}} +w_5 S_{\text{HMM}} +w_6 S_{\text{Hawkes}} +w_7 S_{\text{sweep}}
-w_8 S_{\text{spread}} -w_9 S_{\text{news}} ]
Normalize each component to ([0,1]).
Trade only if:
[ Score \geq 0.72 ]
Suggested hard exclusions override the score:
●
●
●
●
●
●
●
●
Forecast range (\leq150) ticks
Hurst (\leq0.55)
No valid liquidity sweep
No CVD confirmation
Stop distance (>50) ticks
Slippage estimate (>25%) of intended risk
News lockout active
Daily loss or trade count limit reached
14. Backtest Design
A valid test requires:
●
●
Tick-by-tick bid/ask data
Historical depth data if OFI uses displayed liquidity
●
●
●
●
●
●
●
Event timestamps with release times
Actual contract roll dates
Commission
Exchange fees
Bid-ask spread
Queue and limit-order fill assumptions
Slippage stress tests
The backtest must use walk-forward validation:
1. Train on 24 months.
2. Validate on 6 months.
3. Roll forward by 3 months.
4. Repeat across the full 5-year sample.
5. Keep the final year completely untouched as a holdout.
Avoid random train/test splits because they leak time-series information.
Required performance metrics
Do not optimize only win rate. Report:
[ EV
p\bar{W}-(1-p)\bar{L} ]
Also report:
●
●
●
●
●
●
●
●
●
●
●
●
●
●
●
●
●
●
Profit factor
Expectancy per trade
Median winner and loser
95th percentile adverse excursion
95th percentile favorable excursion
Maximum consecutive losses
Maximum daily loss
Maximum trailing drawdown
Probability of violating the internal daily stop
Probability of violating the trailing drawdown
Best-day profit percentage
Average holding time
Limit fill rate
Slippage sensitivity
Performance by session
Performance by rollover week
Performance by news proximity
Performance by volatility regime
At a 42% win rate, a 1:2.5 payoff ratio has a theoretical expectancy before costs of:
[ EV = 0.42(2.5)-0.58(1)=0.47R ]
At a 1:4 payoff ratio:
[ EV = 0.42(4)-0.58(1)=1.10R ]
These are only theoretical values. A limit-entry strategy can have materially lower
realized performance because of missed fills, adverse selection, and stop slippage.
15. Minimal Execution State Machine
FLAT
-> SESSION
CHECK
_
-> NEWS
CHECK
_
-> VOLATILITY
CHECK
_
-> REGIME
CHECK
_
-> LIQUIDITY
SWEEP
CHECK
_
_
-> ORDER
FLOW
CONFIRMATION
_
_
-> PLACE
LIMIT
_
-> FILLED or EXPIRED
-> MANAGE
POSITION
_
-> EXIT
-> DAILY
RISK
CHECK
_
_
The state machine must prevent:
●
More than two trades per session day
●
More than one open position
●
Re-entry after a stopped trade unless the second setup independently satisfies
all conditions
●
Stop widening
●
●
●
●
Position-size increases after a loss
Grid orders
Martingale sizing
Market-order conversion after limit-order expiry
Recommended Initial Parameter Set
Forecast horizon: 60 minutes
Minimum forecast range: 150 GC ticks
OFI window: 10 seconds
OFI confirmation: 2.5 z-score for 3 bars
Volume bar size: 1,000 contracts
Hurst minimum: 0.58 for high-conviction setup
Build probability: > 0.60
Expansion probability: > 0.60
Classifier probability: >= 0.62
Sweep reclaim time: <= 30 seconds
Limit expiry: 20 seconds
Entry location: 50% sweep wick
Stop: structural, max 50 ticks
Target: 100-150 ticks
Trades per day: 2 maximum
Risk per trade: 0.4% default
Internal daily stop: min($1,100, 75% firm DLL)
News lockout: 5 minutes internal
The critical research question is not whether this rule set can produce a 42% win rate
in-sample. It is whether the conditional magnitude edge survives:
●
●
●
●
●
●
●
contract rollover,
realistic limit fills,
news exclusion,
changing volatility,
altered market depth,
different sessions,
and prop-firm risk constraints.
The first production version should therefore trade only the highest-confidence subset,
with 0.4% risk and MGC if GC sizing cannot fit comfortably inside the internal daily-loss
limit.