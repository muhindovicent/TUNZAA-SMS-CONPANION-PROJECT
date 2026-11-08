# ADR 0010: VHTs and facility staff may enrol women

- Status: Accepted
- Date: 2026-10-31

## Context

The original brief assumed only village health team members (VHTs) enrol women. A buyer
decision allows facility staff to enrol directly. Enrolment is a sensitive write that creates
a pregnancy record and captures consent.

## Decision

- VHTs may register women in their own catchment.
- Facility staff may register women linked to their facility and may see women whose home
  facility matches and who consented to facility sharing.
- Facility direct enrolment requires the facility partnership to be on file and does not
  broaden the facility user's scope beyond their facility and consent.
- Consent remains mandatory for the three scopes: `sms`, `vht_followup` and
  `facility_sharing`.
- A woman under 18 cannot be saved without guardian details.
- Every enrolment, consent change and scope denial is audited.

## Consequences

- Role and scope tests must cover both VHT and facility registration paths.
- Facility staff still cannot see unlinked or unconsented women, and exports remain
  aggregate-only with small-cell suppression.
- The registration UI is shared, but the server decides which owning VHT/facility fields are
  permitted for the signed-in role.
