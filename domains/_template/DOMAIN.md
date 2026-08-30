# Domain Card Template

A domain card is an optional research perspective layered on top of one or more
computational SKILLs. It is not a SKILL, it is never executed directly, and it is
never required for the system to operate. It is attached to subagent briefs to
anchor scientific reasoning in a specific application area while remaining
strictly inside the DDM-supported research universe.

Every domain card must answer one question: **which scientific questions are worth
asking within the computational capabilities that the available SKILLs actually
provide.**

## Required sections

### 1. Application target

The material or molecular problem being addressed, stated as an objective, not as
a conclusion.

### 2. Target properties and DDM-computable surrogates

Each property of interest and the exact DDM output that represents it, including
units, protocol, and any known fidelity limitations. A property with no
computable surrogate is out of scope for this card.

### 3. DDM-supported design variable axes

The orthogonal variables that the available SKILLs can actually construct or
perturb (composition, topology, substituent, dopant, dimensionality, defect,
thermodynamic condition). Each axis must cite the SKILL operation that realizes
it.

### 4. Computable mechanism library

A list of candidate mechanisms. Each entry shall be written as a computable
chain:

```text
design variable -> computable descriptor(s) -> simulated property -> expected direction
```

A mechanism without a computable descriptor chain shall not be included.

### 5. Standard contrasts and controls

The matched or single-variable contrasts appropriate for the domain, for example:
same scaffold with one substituent changed; same topology and pore size with one
functional group changed; same composition with one crystal phase changed;
charge-off or interaction-term-off controls; protocol-identity controls.

### 6. Descriptor collinearity and confounders

Known correlations among computable descriptors and the confounders they create.
Each entry shall state how a controlled contrast, rather than a correlation, can
disambiguate the confounder.

### 7. Evidence ladder for this domain

Concrete examples of screening-grade, discrimination-grade, and
confirmation-grade studies: what each grade computes, which scientific decision
it supports, and which decisions it does not support.

### 8. Known null results and literature anchors

Documented null or negative findings that should inform prior expectations, and
citable anchors where available. Each entry shall state the boundary within which
the prior applies.

### 9. Explicitly excluded physics

Physical or engineering variables that the current DDM set cannot represent
(e.g., real synthesis kinetics, processing history, aging, or transport at
unsupported scales). These variables shall not be proposed as Mission objectives
or hypothesis variables while the corresponding DDM capability is absent.

## Usage rules

- The main agent attaches the card to Investigator, Challenger, Test Designer, and
  Mission Synthesizer briefs when a matching card exists.
- The card supplies prior knowledge and question framing only. It cannot override
  the DDM verifiability gate or the frozen-evidence pipeline.
- Experiment Runner receives only the SKILL capability and protocol sections, not
  the domain card.
- If no card exists for an application, agents shall proceed from the SKILL
  capability contracts and their own scientific knowledge under the same DDM
  constraints.
