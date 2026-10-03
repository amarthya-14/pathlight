import type { ProfileOut, ProfileUpsert } from "./types";

/** Full PUT /api/profile body: the current profile with `patch` applied. The endpoint
 * replaces the whole profile, so every save must send every field — otherwise saving
 * one section would silently wipe another. */
export function profilePayload(profile: ProfileOut | null, patch: Partial<ProfileUpsert>): ProfileUpsert {
  return {
    cgpa: profile?.cgpa ?? null,
    branch: profile?.branch ?? null,
    github_username: profile?.github_username ?? null,
    experience_years: profile?.experience_years ?? 0,
    college: profile?.college ?? null,
    graduation_year: profile?.graduation_year ?? null,
    target_roles: profile?.target_roles ?? [],
    preferred_locations: profile?.preferred_locations ?? [],
    open_to_remote: profile?.open_to_remote ?? true,
    expected_ctc_lpa: profile?.expected_ctc_lpa ?? null,
    notice_period: profile?.notice_period ?? null,
    autopilot_enabled: profile?.autopilot_enabled ?? false,
    autopilot_min_match: profile?.autopilot_min_match ?? 75,
    ...patch,
  };
}
