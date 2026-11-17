from competitor_pulse.app.competitors import (
    Competitor,
    CompetitorCreate,
    Snapshot,
    add_competitor,
    list_competitors,
    list_snapshots,
    remove_competitor,
)
from competitor_pulse.app.health import HealthResponse, UnavailableResponse, health_db
from competitor_pulse.configuration import CompetitorPulseConfiguration, DatabaseConfiguration
from competitor_pulse.database import to_sqlalchemy_url

# Pydantic fields, settings and validators are read by Pydantic/FastAPI, not by our code.
Competitor.id
CompetitorCreate.id
Snapshot.fetchedAt
Snapshot.title
Snapshot.tagline
Snapshot.price
Snapshot.description
Snapshot.changed
Snapshot.summary
HealthResponse.status
UnavailableResponse.status
CompetitorPulseConfiguration.model_config
DatabaseConfiguration.model_config
DatabaseConfiguration._max_size_is_not_below_min_size

# Route functions are called by FastAPI.
list_competitors
add_competitor
remove_competitor
list_snapshots
health_db

# Stub endpoints: the parameters are used once the endpoints are implemented.
_.body  # type: ignore[name-defined]  # noqa: F821
_.competitor_id  # type: ignore[name-defined]  # noqa: F821

# Used by migrations/env.py, which vulture does not scan.
to_sqlalchemy_url
