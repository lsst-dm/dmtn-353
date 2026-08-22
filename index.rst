##############################
User data download for the RSP
##############################

.. abstract::

   Users of the Rubin Science Platform need a simple, rate-limited mechanism to download files, both from data products such as data releases and from various other project sources such as ad hoc supporting files that may not be registered with the Butler.
   Those downloads may need to be routed to specific Data Facilities to minimize network charges for Rubin Observatory.
   This tech note discusses requirements and design options for a service to fill this gap.

Current status
==============

When this tech note was first written (August 2026), user download of data products followed one of two paths:

#. Download via a signed URL from the Butler server.
   This signed URL could be generated directly by using a Butler client (from, for example, a notebook or a local laptop), or, more commonly, via the DataLink links endpoint returned from ObsCore searches, SIA, etc.
   (See :dmtn:`238` for more information about the DataLink service.)

#. Manual download via a variety of mechanisms (:command:`scp`, download from the JupyterLab UI, etc.) of files stored in the NFS file system mounted on :file:`/rubin` in the Notebook Service.

Official data products (primarily images) are available through the first route.
All other files are available, awkwardly and without a consistent publishing policy, through the second route, if at all.

Early Data Preview 2 was released with hybrid storage locations.
All images are stored at the US Data Facility at SLAC, and some images were replicated to Google Cloud Storage.
The Butler server knows which classes of images are available in which locations and chooses to hand back signed URLs for either Google Cloud Storage or SLAC's object store, depending on the type of requested image.

At present, there is effectively no rate limiting on any of these download mechanisms.

Problem statement
=================

There are several related issues that we hope to fix.

.. _download-service:

Download service
----------------

Rubin Observatory needs a way to make available for user download various files that do not fit neatly into the current data collections.
These include one-off data products, supporting files, and derived data products of general interest produced by observatory staff and of interest to data rights holders.
These files may or may not be associated with a specific data release, and they may or may not be stored in the Butler.

We anticipate three phases of requirements for a download service:

**Phase one: Butler files**
    Allow users to download files, via a static URL that does not expire, additional files that are not part of a specific data release but can be stored in the Butler.
    These are, in the general case, files that are not usefully discoverable via IVOA protocols.
    We want to be able to provide a static URL to a user and allow the user to retrieve the file from that URL after appropriate authentication and data rights checks.
    For this phase, all files should be hosted at the USDF at SLAC, not in Google Cloud Storage, since we want to avoid any potential egress charges for serving them.

**Phase two: Non-Butler files**
    This is the same basic requirement as phase one, but extended to files that cannot be meaningfully stored in a Butler collection.
    This may be because the required associated metadata would be meaningless for them, or because ingesting them into a Butler collection is too much hassle for the benefit.

**Phase three: Choose appropriate download locations**
    For future work, with no currently planned date, we would ideally like to be able to route the user's request to an appropriate geographically-aware download location.
    For instance, if the file is replicated at the US Data Facility and the UK Data Facility, a user requesting the file from the US should be routed to the USDF object store and a user requesting the file from the UK should be routed to the UKDF object store.

For all phases, a given file should have a fixed, simple URL that's easy to convey to the user.
Accesses to that URL should go through normal Rubin Science Platform authentication and data rights checks before redirecting to a signed URL that allows the user to directly download the file from the underlying data store.
This redirected signed URL should have a very short lifetime (on the order of fifteen minutes) so that it cannot be usefully shared with other users and all uesrs need to go through the authentication and authorization checks of the static, published URL.

.. _persistent-urls:

Persistent URLs for data products
---------------------------------

Currently, the closest that the Rubin Science Platform has to a persistent URL for a single Butler dataset is its Butler ID (IVOID).
With that identifier, the user can retrieve the DataLink links document for that object, which contains an expiring signed URL from which it can be retrieved.

This is inconvenient for several reasons:

- The DataLink links document exposes the underlying signed URL to the user, implying that it is a useful URL for that object, but it then expires, possibly confusing the user and preventing sharing the URL with other users.

- For so long as the signed URL persists, it can be passed to people without data rights, and they do not have to authenticate to the Rubin Science Platform to access that dataset.

- Users cannot easily publish a persistent URL to a specific dataset of interest, reference it in other communications, save it for later processing, or take similar actions that users generally expect to be able to do with a URL.

Ideally, the DataLink links document, and other sources of URLs for datasets, should provide a persistent URL for that object.
That URL should require authentication and authorization checks each time it is accessed and transparently redirect, behind the scenes, to an appropriate short-lived object store URL that the user can ignore.

Rate limiting of all user downloads
-----------------------------------

Full LSST data releases will be extremely large.
Some ambitious users may wish to download large portions of that data release.
We want to allow this, within reason, but we cannot allow huge downloads to interfere with other uses of the Rubin Science Platform or underlying data stores, or to incur unexpected and potentially large bandwidth charges for Rubin Observatory.

We therefore want to apply rate limiting to users so that the quantity of data they can download from Rubin Data Facilities does not cause problems for either the data facility or for other users.

Applying rate limiting in the underlying object store would be ideal since it knows exactly how many bytes have been retrieved, but this requires making it aware of the identity of users so that downloads can be debited from an appropriate quota.
This is quite challenging; by design, the underlying object stores should not have to interact with Rubin Science Platform authentication methods, since this would add substantial operational complexity.
We therefore need to apply rate limits at some point upstream of the object store that is part of the Rubin Science Platform (and therefore knows the authenticated user identity) but can still make a reasonable guess about how much the user is downloading.

The service that generates the signed URL for the user seems like a reasonable point at which to do this.
We can make the simplifying and conservative assumption that the user will download the resource on the other end of a signed URL approximately once per issuence of a signed URL provided that we make the lifetime of those signed URLs sufficiently short that the URL can't be reasonably stored or reused.
The service providing signed URLs can then decide whether to allow a given request or reject it with an HTTP rate limiting error code based on the recent past history of signed URL generation for that user.

If the other components of the Rubin Science Platform return a persistent URL to a separate data download service (see :ref:`persistent-urls`), rather than generating signed URLs themselves, this both allows addressing quotas in a single place and avoids requiring other services propagate appropriate HTTP error codes through a complex call chain.

Choosing appropriate hosting locations
--------------------------------------

Even when the user is downloading datasets that are part of an official data release, not just the more ad hoc cases anticipated by :ref:`download-service`, we want to direct the user to an appropriate download location that minimizes latency for the user and cost for Rubin Observatory.

For example, users working within the Rubin Science Platform hosted at Google should preferentially be directed to data stored in Google Cloud Storage, if possible.
This minimizes latency and often falls under egress exceptions since the data is used internally within Google Cloud Platform.
However, users requesting data products through APIs from their laptop should preferentially be directed to the US Data Facility for direct download, even if the service from which they are requesting the data is hosted on Google Cloud Platform.
This avoids egress charges for serving data from Google Cloud Platform to external users.

This is a special case of the general geolocation decision-making anticipated by phase three of the download service (see :ref:`download-service`).

Proposed implementation
=======================

The following high-level design fulfills the above requirements:

.. diagrams:: implementation.py

The user flow for requesting an image remains the same as the current design up through the Butler server.
However, instead of handing back a signed URL to the underlying storage as in the current design, the Butler server hands back a URL to the download service.
This URL is then provided to the user or intermediate service (such as the Portal Aspect) via DataLink.
The download service is then responsible for turning that request into a signed URL for the underlying storage and redirecting the user's request to that signed URL.

In this design, the Butler server does not talk directly to the download service and the download service does not talk directly to the object store.
Rather, the communications shown by dotted lines in the diagram are done via redirects, causing the user's client to make a separate HTTP request to the other service with a new URL.

The separate download service that the user can reach directly opens the possibility for the user to request a file from the download service directly without using the Butler or DataLink.
This addresses the use cases for arbitrary file download for files that may not make sense to import into the Butler.
The mapping of download URL to underlying object store location is maintained in a separate database for the download service and can be updated via an API.
This is akin to a link shortening service, except that the destination is an object store path rather than an arbitrary URL.

Complication: Authorization
---------------------------

Responsibility for authorization checking for files associated with a data release rests with the Butler (see :dmtn:`182`).
Paths to files within the object store currently have no authorization-relevant structure; for example, it is not possible to determine the data release from the object store path.
The download service therefore cannot take responsibility for the authorization checks since the checks require knowledge only available to the Butler.
This means the authorization information has to be conveyed from the Butler service to the download service, but those two services do not directly talk to each other.

One solution to this problem would be for the Butler server to return signed URLs for the download service, indicating that the authorization check has already been performed.
The download service would then verify the signature and issue a new signed URL for the underlying object store.
This, however, reintroduces the problem of signed URL lifetime: The URLs returned by the Butler and thus by DataLink are no longer persistent and cannot be used after the signature expires, and that expiration time must be shorter than the time frame in which the system should respond to changes in authorization.

Complication: Choosing a storage backend
----------------------------------------

The download service will need, in the general case, to be able to issue signed URLs for multiple backend object stores.
Most requests will be sent to the USDAC, since we believe it will be the most cost-efficient object store for Rubin Observatory to serve file downloads from.
However, requests within the Rubin Science Platform hosted at Google for resources that are also stored or cached at Google should be sent to Google Cloud Storage instead for improved request latency.

The download service therefore must be aware both of where objects are stored and where the request is coming from.
Requests from outside the Rubin Science Platform (such as from user laptops) should, in the general case, be directed to the USDAC.
Requests from inside the Rubin Science Platform (such as from the Notebook Aspect) should be directed to Google Cloud Storage if the requested file is available from there, or to the USDAC if it is not.
It is not clear what policy should be used for requests from the Portal, since it is both a service located within the Rubin Science Platform and provides the URLs to the user for use outside the Rubin Science Platform.

The Butler server is the component that knows where files are located.
It therefore should be responsible for communicating that information to the download service for the case of files that are part of a data release or are otherwise reigstered in the Butler.
This, in turn, implies that the Butler server needs information about where the request originates from so that it can make policy decisions about whether to direct the user to Google Cloud Storage or to the USDAC, even after the final URL signing and redirect is handled by the download service.
The disadvantage of this approach is that the URLs returned via DataLink will encode a specific backend location and cannot later be served from a different location without being reissued.
This design is also complicated by the fact that users normally do not talk to the Butler server directly and instead retrieve URLs via the DataLink service
The Butler server sees the request as coming from the DataLink service, which is internal to the Rubin Science Platform.

Solving this properly will probably require addition of a way to pass the location of the client through the Butler client/server protocol from the DataLink service.
Or, alternately, the URL to the download service returned by the Butler must contain enough information that the download service can make an independent determination of what storage backend to use to satisfy the request.

For objects not stored in the Butler, the situation is simpler: When the persistent URLs for those objects are registered, information about the object store used to satisfy the request can be stored with the registered object store path, including separate paths for multiple object stores as needed if the backend should vary based on the location of the client.

Implementation phases
=====================

Implementing this design can happen in several phases.

Phase 0: No code changes (optional)
-----------------------------------

The most expedient way to make files available for download without requiring any development work is:

#. Create a new Butler repository for files not associated with any data release and add it to the Repertoire configuration.
#. Publish DataLink URLs to retrieve records for those files by Butler IVOID.
#. Document how to extract the actual signed URL from the DataLink XML to download the underlying file.

This allows us to serve any file that can be ingested into the Butler, but the user experience is not great (have to retrieve a DataLink XML document and parse it to find an expiring temporary URL).

Phase 1: Download service for arbitrary files
---------------------------------------------

Implement a download service, a backing database for mappings of URLs to object store locations, and signing code and credentials for at least the USDAC object store.
When deployed, this would allow simpler download of arbitrary artifacts stored at the USDAC, and optionally could also support Google Cloud Storage.

For this phase, there would be no changes to Butler.
Downloads of objects from the Butler (including via DataLink) would still be done via temporary URLs signed by Butler itself.

This initial version of the download service would also have metrics and quota support.
Initial quota support would be by total bytes per unit time of the files for which it returns links.
We will have to decide on a time period across which the quota limit applies.
One minute probably isn't useful when returning pre-signed URLs; an hour or a day probably captures the desired limit more cleanly.

Phase 2: Point Butler at the download service
---------------------------------------------

Start returning URLs for the download service from Butler, and thus from DataLink.

This requires download service support for arbitrary data release files that aren't pre-registered and assigned a static URL.
This also requires resolving the problem with authorization of download of data release files, either by having Butler sign URLs to include authorization information or finding a way for the download service to separately check authorization.

In this phase, the Butler server would convey the backend storage location (Google Cloud Storage or USADC) to the download service as part of the URL in some way, or alternately only use the download service for files that Butler wants to serve from the USDAC.

Phase 3: Add client location information
----------------------------------------

Allow the choice of storage backend to be driven by the location of the client.
Determine whether the client request came from inside or outside the Rubin Science Platform and route download requests for files dual-hosted in both Google Cloud Storage and at the USDAC accordingly.

At this phase, resolve whether this information needs to be conveyed to Butler somehow so that it can embed the correct location for data products in the redirect to the download service, or whether the download service can be taught enough about the locations of files that it can apply this logic directly.
