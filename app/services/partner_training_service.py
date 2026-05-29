"""Partner training video catalog (DO Spaces URLs — active partners only)."""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class PartnerTrainingVideo:
    title: str
    description: str
    url: str


PARTNER_TRAINING_VIDEOS: tuple[PartnerTrainingVideo, ...] = (
    PartnerTrainingVideo(
        title="LeadCareAI Sales Playbook",
        description=(
            "Full sales playbook for new reps: product overview, how missed-call recovery works, "
            "demo flow, referral links, and what to say to local service businesses."
        ),
        url="https://our-cloud-storage.sfo3.cdn.digitaloceanspaces.com/leadcareai/marketing/video/LeadCareAI_Sales_Playbook.mp4",
    ),
)


def list_partner_training_videos() -> list[PartnerTrainingVideo]:
    return list(PARTNER_TRAINING_VIDEOS)
