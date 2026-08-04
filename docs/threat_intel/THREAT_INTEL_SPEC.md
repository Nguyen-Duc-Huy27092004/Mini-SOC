# Threat Intelligence Aggregator & IOC Scoring Specification
## Enterprise Mini SOC Platform

### 1. Multi-Feed Cross-Validation Policy
Per Threat Intel Golden Rules, **No automated action or high severity tagging shall occur based on a single feed alone**. IOC reputation scores MUST be cross-validated across multiple providers:

```
┌─────────────────────────────────────────────────────────────┐
│                 Threat Intel Enrichment Engine               │
│                                                             │
│   ┌──────────────┐   ┌──────────────┐   ┌──────────────┐   │
│   │ VirusTotal   │   │ AbuseIPDB    │   │ AlienVault   │   │
│   │ (40% Weight) │   │ (40% Weight) │   │ (20% Weight) │   │
│   └──────┬───────┘   └──────┬───────┘   └──────┬───────┘   │
└──────────┼──────────────────┼──────────────────┼────────────┘
           │                  │                  │
           └──────────────────┼──────────────────┘
                              ▼
            [ Composite Confidence Score: 0-100 ]
                              │
           ┌──────────────────┴──────────────────┐
           │ Score >= 80: High Malicious Confidence│
           │ Score 40-79: Suspicious / Watchlist  │
           │ Score < 40: Benign / Clean            │
           └─────────────────────────────────────┘
```

---

### 2. Composite Confidence Score Calculation Formula
$$\text{Composite Score} = (0.40 \times \text{VT\_Malicious\_Ratio}) + (0.40 \times \text{AbuseIPDB\_Confidence}) + (0.20 \times \text{OTX\_Pulse\_Weight})$$

- **VirusTotal Ratio:** $(\text{Positives} / \text{Total Engines}) \times 100$
- **AbuseIPDB Score:** Direct confidence score (0-100%) from API response.
- **OTX Weight:** 100 if present in verified pulses, else 0.
