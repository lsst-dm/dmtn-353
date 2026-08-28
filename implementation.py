"""Source for implementation.png component diagram."""

import os

from diagrams import Cluster, Diagram, Edge
from diagrams.gcp.compute import KubernetesEngine
from diagrams.gcp.database import SQL
from diagrams.gcp.network import LoadBalancing
from diagrams.gcp.storage import PersistentDisk, GCS
from diagrams.generic.storage import Storage
from diagrams.onprem.client import User
from diagrams.onprem.compute import Server
from diagrams.programming.framework import React

graph_attr = {
    "label": "",
    "nodesep": "0.2",
    "pad": "0.2",
    "ranksep": "0.75",
    "splines": "spline",
}

node_attr = {
    "fontsize": "12.0",
}

with Diagram(
    "Download service design",
    show=False,
    filename="implementation",
    outformat="png",
    graph_attr=graph_attr,
    node_attr=node_attr,
):
    user = User("End user")

    with Cluster("Google"):
        with Cluster("Science Platform"):
            notebook = KubernetesEngine("Nublado notebook")
            portal = KubernetesEngine("Portal")
            datalink = KubernetesEngine("DataLink")
            butler = KubernetesEngine("Butler")
            download = KubernetesEngine("Download service")

        butlerdb = SQL("Butler DB")
        downloaddb = SQL("Link database")
        gcs = GCS("Object store")

    with Cluster("USDAC"):
        converter = KubernetesEngine("Format converter")
        storage = Storage("Object store")

    user >> [notebook, portal] >> datalink >> butler
    user >> download
    user >> gcs
    user >> storage
    user >> converter >> storage
    butler >> butlerdb
    download >> downloaddb

    butler >> Edge(style="dashed") >> download
    download >> Edge(style="dashed") >> gcs
    download >> Edge(style="dashed") >> converter
    download >> Edge(style="dashed") >> storage

    # Force better formatting.
    notebook >> Edge(style="invis") >> converter
    butlerdb >> Edge(style="invis") >> converter
