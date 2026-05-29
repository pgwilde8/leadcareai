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
            "Start here — full sales playbook for new reps: product overview, how missed-call recovery "
            "works, demo flow, referral links, and what to say to local service businesses."
        ),
        url="https://our-cloud-storage.sfo3.cdn.digitaloceanspaces.com/leadcareai/training-sales/LeadCareAI_Sales_Playbook%20(1).mp4",
    ),
    PartnerTrainingVideo(
        title="The missed call problem",
        description=(
            "Why missed calls cost local service businesses money, and why instant text-back matters "
            "before you pitch the product."
        ),
        url="https://our-cloud-storage.sfo3.cdn.digitaloceanspaces.com/leadcareai/training-sales/The_Missed_Call_Problem.mp4",
    ),
    PartnerTrainingVideo(
        title="Handling objections",
        description=(
            "How to respond to common prospect objections — changing numbers, answering services, "
            "AI concerns, pricing, and carrier forwarding."
        ),
        url="https://our-cloud-storage.sfo3.cdn.digitaloceanspaces.com/leadcareai/training-sales/objections.mp4",
    ),
)


def list_partner_training_videos() -> list[PartnerTrainingVideo]:
    return list(PARTNER_TRAINING_VIDEOS)
