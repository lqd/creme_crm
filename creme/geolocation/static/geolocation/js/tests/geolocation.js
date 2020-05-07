/* globals QUnitGeolocationMixin */
(function($, QUnit) {
"use strict";

QUnit.module("creme.geolocation", new QUnitMixin(QUnitEventMixin,
                                                 QUnitAjaxMixin,
                                                 QUnitGeolocationMixin, {
    beforeEach: function() {
        var self = this;
        var backend = this.backend;
        backend.options.enableUriSearch = true;

        this.mockAddressInfo = {};

        this.setMockBackendGET({
            'mock/addressinfo': this.backend.response(200, $.toJSON(this.mockAddressInfo))
        });

        this.setMockBackendPOST({
            'mock/addressinfo': function(url, data, options) {
                self.mockAddressInfo = data || {};
                return backend.response(200, $.toJSON(self.mockAddressInfo));
            }
        });

        this.mockGeocoder = this.createMockGoogleGeocoder();
    },

    runTestOnGeomapReady: function(controller, element, callback) {
        this.bindTestOn(controller, 'status-enabled', callback, [controller]);

        controller.bind(element);
        equal(true, controller.isBound());

        stop(1);
    }
}));

QUnit.test('creme.geolocation.Location (defaults)', function() {
    var location = new creme.geolocation.Location();
    equal(undefined, location.id());
    equal('', location.content());
    equal('', location.title());
    equal(undefined, location.owner());
    equal(undefined, location.url());

    equal(false, location.visible());
    equal(null, location.position());
    equal(false, location.hasPosition());

    equal(creme.geolocation.LocationStatus.UNDEFINED, location.status());
    equal(false, location.isComplete());
    equal(false, location.isPartial());
    equal(false, location.isManual());

    equal(gettext("Not localized"), location.statusLabel());
    equal('', location.positionLabel());
    equal('', location.markerLabel());
});

QUnit.test('creme.geolocation.Location (getters)', function() {
    var location = new creme.geolocation.Location({
        id: 'A',
        content: '319 Rue Saint-Pierre, 13005 Marseille',
        title: 'Address A',
        owner: 'joe',
        url: 'mock/address/Address_A',
        visible: true,
        status: creme.geolocation.LocationStatus.PARTIAL,
        position: {lat: 43.45581, lng: 5.544}
    });

    equal('A', location.id());
    equal('319 Rue Saint-Pierre, 13005 Marseille', location.content());
    equal('Address A', location.title());
    equal('joe', location.owner());
    equal('mock/address/Address_A', location.url());

    equal(true, location.visible());
    deepEqual({lat: 43.45581, lng: 5.544}, location.position());
    equal(true, location.hasPosition());

    equal(creme.geolocation.LocationStatus.PARTIAL, location.status());
    equal(false, location.isComplete());
    equal(true, location.isPartial());
    equal(false, location.isManual());

    equal(gettext("Partially matching location"), location.statusLabel());
    equal('43.455810, 5.544000', location.positionLabel());
    equal('joe\nAddress A', location.markerLabel());
});

QUnit.test('creme.geolocation.Location (copy)', function() {
    var location = new creme.geolocation.Location({
        id: 'A',
        content: '319 Rue Saint-Pierre, 13005 Marseille',
        title: 'Address A',
        owner: 'joe',
        url: 'mock/address/Address_A',
        status: creme.geolocation.LocationStatus.COMPLETE,
        position: {lat: 43, lng: 5}
    });

    var copy = new creme.geolocation.Location(location);

    deepEqual(copy, location);
});

QUnit.test('creme.geolocation.Location (position)', function() {
    var location = new creme.geolocation.Location({
        position: {lat: 43, lng: 5}
    });

    equal(true, location.hasPosition());
    deepEqual({lat: 43, lng: 5}, location.position());

    location = new creme.geolocation.Location({
        latitude: 42, longitude: 6
    });

    equal(true, location.hasPosition());
    deepEqual({lat: 42, lng: 6}, location.position());

    location = new creme.geolocation.Location({
        latitude: 42,
        longitude: 6,
        position: {lat: 43, lng: 5}
    });

    equal(true, location.hasPosition());
    deepEqual({lat: 42, lng: 6}, location.position());
});

QUnit.test('creme.geolocation.Location (status)', function() {
    var location = new creme.geolocation.Location({
        status: creme.geolocation.LocationStatus.COMPLETE
    });

    equal(creme.geolocation.LocationStatus.COMPLETE, location.status());
    equal(true, location.isComplete());
    equal(false, location.isPartial());
    equal(false, location.isManual());
    equal('', location.statusLabel());

    location = new creme.geolocation.Location({
        status: creme.geolocation.LocationStatus.PARTIAL
    });

    equal(creme.geolocation.LocationStatus.PARTIAL, location.status());
    equal(false, location.isComplete());
    equal(true, location.isPartial());
    equal(false, location.isManual());
    equal(gettext("Partially matching location"), location.statusLabel());

    location.status(creme.geolocation.LocationStatus.MANUAL);

    equal(creme.geolocation.LocationStatus.MANUAL, location.status());
    equal(false, location.isComplete());
    equal(false, location.isPartial());
    equal(true, location.isManual());
    equal(gettext("Manual location"), location.statusLabel());
});

}(jQuery, QUnit));