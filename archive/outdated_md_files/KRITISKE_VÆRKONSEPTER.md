# KRITISKE VÆRKONSEPTER - LES DETTE FØRST!

## 🚨 GLATTFØRE-LOGIKK (må huskes!)

### Nedbørtype-deteksjon:
- **REGN** = minkende snømengde på måleren (snøen smelter)
- **SLUDD** = stabil snømengde på måleren 
- **SNØ** = økende snømengde på måleren

### VIKTIG UNNTAK:
- **Ved minusgrader** kan snømengde-endringer skyldes **vindblåst snø** (IKKE nedbørtype)
- Da må vi være forsiktige med å tolke endringer som regn/sludd/snø

### Glattføre-kriterier:
- **GLATTFØRE varsles KUN ved REGN** (ikke snø/sludd)
- **Høy risiko:** temp > +2°C + nedbør + snømengde_endring < 0 (minkende = regn)
- **Medium risiko:** temp > +2°C etter frost
- **IKKE bruk snødybde** som kriterium for glattføre
- **BRUK ALDRI "regn på snø"** som begrep - det er bare **REGN**
- **REGN kan IKKE være ved minusgrader** - da er det snø!

### Implementering:
```python
def detect_slippery_conditions(temp, precipitation, snow_depth_change):
    """
    Detekterer glattføre basert på REGN (ikke regn på snø!)
    """
    # Regn = minkende snømengde + nedbør + temp OVER +2°C
    if temp > 2 and precipitation > 0.2 and snow_depth_change < 0:
        return "high", "Regn som skaper glattføre"
    
    # Mildvær etter frost
    if temp > 2:
        return "medium", "Mildvær etter frost"
    
    return "low", "Ingen glattføre-risiko"
```

## 🌨️ SNØFOKK-LOGIKK

### Kriterier:
- **Vindkjøling** (temp - vind*2) 
- **Vindstyrke**
- **Snømengde** (for løs snø som kan blåses)

### Ikke bruk:
- Snødybde-endring for snøfokk (det er for glattføre/regn-deteksjon)

---

**HUSK:** Glattføre = REGN. Ikke snø, ikke sludd, ikke "regn på snø". Bare REGN.
