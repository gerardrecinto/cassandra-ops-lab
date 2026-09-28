from cassandra.cluster import Cluster, Session
from cassandra.policies import DCAwareRoundRobinPolicy


def get_cluster(contact_points: list[str], local_dc: str = "dc1") -> Cluster:
    return Cluster(
        contact_points=contact_points,
        load_balancing_policy=DCAwareRoundRobinPolicy(local_dc=local_dc),
    )


def get_session(contact_points: list[str], keyspace: str | None = None) -> Session:
    cluster = get_cluster(contact_points)
    session = cluster.connect()
    if keyspace:
        session.set_keyspace(keyspace)
    return session
