"""Proxy listener stub — mitmproxy integration deferred.

This module defines the :class:`ProxyListener` interface that will
capture live traffic via mitmproxy when implemented. The integration
is deferred; see PROPOSAL.md §16.1 for the roadmap entry.

Ref: PROPOSAL.md §11.1, §16.1
"""

from __future__ import annotations


class ProxyListener:
    """Intercept HTTP traffic via an embedded mitmproxy instance.

    .. note::
        **Not yet implemented.** mitmproxy integration is deferred to a
        future milestone. See ``PROPOSAL.md §16.1``.

    When implemented, :meth:`start` will launch a local proxy on a
    configurable port and feed captured :class:`~src.input.models.HttpExchange`
    objects into the analysis pipeline in real time.
    """

    def start(self) -> None:
        """Start the proxy listener.

        Raises:
            NotImplementedError: Always — mitmproxy integration is deferred.
        """
        raise NotImplementedError(
            "mitmproxy integration deferred — see PROPOSAL.md §16.1"
        )

    def stop(self) -> None:
        """Stop the proxy listener.

        Raises:
            NotImplementedError: Always — mitmproxy integration is deferred.
        """
        raise NotImplementedError(
            "mitmproxy integration deferred — see PROPOSAL.md §16.1"
        )
