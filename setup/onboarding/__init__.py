"""Onboarding: user profile questionnaire before system scan."""

from setup.onboarding.profile import UserProfile, default_profile_path
from setup.onboarding.questionnaire import run_questionnaire

__all__ = ["UserProfile", "default_profile_path", "run_questionnaire"]
