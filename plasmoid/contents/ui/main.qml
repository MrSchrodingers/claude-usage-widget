import QtQuick
import QtQuick.Layouts
import QtQuick.Controls as QQC2
import org.kde.plasma.plasmoid
import org.kde.plasma.plasma5support as P5Support
import org.kde.plasma.components as PlasmaComponents3
import org.kde.plasma.extras as PlasmaExtras
import org.kde.kirigami as Kirigami

PlasmoidItem {
    id: root

    property var usageData: ({})
    property bool hasData: Object.keys(usageData).length > 0
    property var activeIncidents: {
        var inc = usageData.serviceStatus?.active_incidents ?? [];
        return inc.length > 0 ? [inc[0]] : [];
    }
    property int dumbScore: usageData.dumbness?.score ?? 0
    property string dumbLevel: usageData.dumbness?.level ?? "genius"
    property bool isDumb: dumbScore >= 25

    readonly property int refreshInterval: 30000

    // Claude palette
    readonly property color claudeAmber: "#D97706"
    readonly property color claudeAmberLight: "#F59E0B"
    readonly property color claudeAmberDim: "#92400E"
    readonly property color blueAccent: "#3B82F6"
    readonly property color greenAccent: "#10B981"
    readonly property color redAlert: "#EF4444"
    readonly property color cardBg: Qt.rgba(Kirigami.Theme.textColor.r, Kirigami.Theme.textColor.g, Kirigami.Theme.textColor.b, 0.05)
    readonly property color subtleBorder: Qt.rgba(Kirigami.Theme.textColor.r, Kirigami.Theme.textColor.g, Kirigami.Theme.textColor.b, 0.08)

    switchWidth: Kirigami.Units.gridUnit * 20
    switchHeight: Kirigami.Units.gridUnit * 28

    toolTipMainText: "Claude Usage"
    toolTipSubText: {
        if (!hasData) return "Loading...";
        var p = usageData.rateLimits?.session?.percentUsed ?? 0;
        var base = "Session: " + Math.round(p) + "% | Weekly: " +
                   Math.round(usageData.rateLimits?.weeklyAll?.percentUsed ?? 0) + "%";
        var status = usageData.serviceStatus?.description ?? "";
        return (status && status !== "All Systems Operational") ? base + "\n⚠ " + status : base;
    }

    // ─── Data ───
    Timer {
        interval: root.refreshInterval
        running: true; repeat: true; triggeredOnStart: true
        onTriggered: dataLoader.readData()
    }

    P5Support.DataSource {
        id: dataLoader
        engine: "executable"
        connectedSources: []
        function readData() {
            connectSource("$HOME/.local/bin/claude-usage-collector.py 1>/dev/null 2>/dev/null; cat $HOME/.claude/widget-data.json");
        }
        onNewData: function(source, data) {
            if (data["exit code"] === 0 && data.stdout) {
                try { root.usageData = JSON.parse(data.stdout.trim()); } catch(e) {}
            }
            disconnectSource(source);
        }
    }

    // ─── Helpers ───
    function formatTokens(n) {
        if (!n) return "0";
        if (n >= 1e9) return (n/1e9).toFixed(1) + "B";
        if (n >= 1e6) return (n/1e6).toFixed(1) + "M";
        if (n >= 1e3) return (n/1e3).toFixed(0) + "K";
        return n.toString();
    }

    function limitColor(pct) {
        if (pct > 80) return redAlert;
        if (pct > 50) return claudeAmberLight;
        return Kirigami.Theme.textColor;
    }

    function barFill(pct, base) {
        if (pct > 80) return redAlert;
        if (pct > 50) return claudeAmberLight;
        return base;
    }

    function statusColor(indicator) {
        if (indicator === "none") return greenAccent;
        if (indicator === "minor") return claudeAmberLight;
        if (indicator === "major") return "#F97316";
        if (indicator === "critical") return redAlert;
        return Qt.rgba(Kirigami.Theme.textColor.r, Kirigami.Theme.textColor.g, Kirigami.Theme.textColor.b, 0.4);
    }

    function componentStatusColor(status) {
        if (status === "operational") return greenAccent;
        if (status === "degraded_performance") return claudeAmberLight;
        if (status === "partial_outage") return "#F97316";
        if (status === "major_outage") return redAlert;
        return Qt.rgba(Kirigami.Theme.textColor.r, Kirigami.Theme.textColor.g, Kirigami.Theme.textColor.b, 0.4);
    }

    // ─── Panel (Compact) ───
    compactRepresentation: MouseArea {
        Layout.minimumWidth: compactRow.implicitWidth
        Layout.preferredWidth: compactRow.implicitWidth
        hoverEnabled: true
        onClicked: root.expanded = !root.expanded

        RowLayout {
            id: compactRow
            anchors.fill: parent
            spacing: Kirigami.Units.smallSpacing

            // Claude logo — smallMedium for better visibility
            Image {
                source: Qt.resolvedUrl("../icons/claude-logo.svg")
                Layout.preferredWidth: Kirigami.Units.iconSizes.smallMedium
                Layout.preferredHeight: Kirigami.Units.iconSizes.smallMedium
                sourceSize: Qt.size(Kirigami.Units.iconSizes.smallMedium, Kirigami.Units.iconSizes.smallMedium)
                fillMode: Image.PreserveAspectFit
            }

            // Session percentage — bigger and bolder
            PlasmaComponents3.Label {
                property real pct: root.usageData.rateLimits?.session?.percentUsed ?? 0
                text: root.hasData ? Math.round(pct) + "%" : "--"
                font.pixelSize: Kirigami.Theme.defaultFont.pixelSize * 1.15
                font.weight: Font.Bold
                color: limitColor(pct)
            }

            // Session bar — taller for prominence
            Rectangle {
                Layout.preferredWidth: 34; Layout.preferredHeight: 5
                Layout.alignment: Qt.AlignVCenter
                radius: 3
                color: root.subtleBorder
                Rectangle {
                    property real pct: root.usageData.rateLimits?.session?.percentUsed ?? 0
                    width: parent.width * Math.min(1, pct / 100)
                    height: parent.height; radius: 3
                    color: barFill(pct, root.claudeAmber)
                    Behavior on width { NumberAnimation { duration: 400; easing.type: Easing.OutCubic } }
                }
            }

            // Service health: dot + short label when not Healthy
            RowLayout {
                id: statusCompact
                property string indicator: root.usageData.serviceStatus?.indicator ?? "none"
                visible: root.hasData && indicator !== "none" && indicator !== "" && indicator !== "unknown"
                spacing: 3
                Layout.alignment: Qt.AlignVCenter

                Rectangle {
                    id: compactDot
                    width: 8; height: 8; radius: 4
                    color: statusColor(statusCompact.indicator)
                    Layout.alignment: Qt.AlignVCenter

                    SequentialAnimation on opacity {
                        running: statusCompact.indicator === "major" || statusCompact.indicator === "critical"
                        loops: Animation.Infinite
                        NumberAnimation { to: 0.2; duration: 650; easing.type: Easing.InOutSine }
                        NumberAnimation { to: 1.0; duration: 650; easing.type: Easing.InOutSine }
                    }
                }

                PlasmaComponents3.Label {
                    text: {
                        var ind = statusCompact.indicator;
                        if (ind === "minor")    return "Degraded";
                        if (ind === "major")    return "Outage";
                        if (ind === "critical") return "Critical";
                        return "";
                    }
                    font.pixelSize: Kirigami.Theme.defaultFont.pixelSize * 0.80
                    font.weight: Font.DemiBold
                    color: statusColor(statusCompact.indicator)
                }
            }
        }
    }

    // ─── Popup (Full) ───
    fullRepresentation: PlasmaExtras.Representation {
        Layout.preferredWidth: Kirigami.Units.gridUnit * 24
        Layout.preferredHeight: Kirigami.Units.gridUnit * 40
        Layout.minimumWidth: Kirigami.Units.gridUnit * 20
        Layout.maximumHeight: Kirigami.Units.gridUnit * 44

        header: PlasmaExtras.PlasmoidHeading { visible: false }

        Flickable {
            id: popupFlick
            anchors.fill: parent
            contentWidth: width
            contentHeight: mainCol.implicitHeight + Kirigami.Units.largeSpacing * 2
            clip: true

            ColumnLayout {
                id: mainCol
                x: Kirigami.Units.largeSpacing
                y: Kirigami.Units.largeSpacing
                width: popupFlick.width - Kirigami.Units.largeSpacing * 2
                spacing: Kirigami.Units.mediumSpacing

            // ══════════════════════════════════
            // ── Header with mascot ──
            // ══════════════════════════════════
            RowLayout {
                Layout.fillWidth: true
                spacing: Kirigami.Units.mediumSpacing

                // Mascot: Clawd (healthy) or Burrinho (degraded)
                Image {
                    source: root.isDumb
                        ? Qt.resolvedUrl("../icons/burrinho.svg")
                        : Qt.resolvedUrl("../icons/clawd.svg")
                    Layout.preferredWidth: Kirigami.Units.iconSizes.huge
                    Layout.preferredHeight: Kirigami.Units.iconSizes.huge
                    sourceSize: Qt.size(Kirigami.Units.iconSizes.huge, Kirigami.Units.iconSizes.huge)
                    fillMode: Image.PreserveAspectFit

                    // Wobble animation when dumb
                    SequentialAnimation on rotation {
                        running: root.isDumb
                        loops: Animation.Infinite
                        NumberAnimation { to: -8; duration: 400; easing.type: Easing.InOutSine }
                        NumberAnimation { to: 8;  duration: 400; easing.type: Easing.InOutSine }
                    }
                }

                ColumnLayout {
                    spacing: 1
                    PlasmaComponents3.Label {
                        text: "Claude"
                        font.pixelSize: Kirigami.Theme.defaultFont.pixelSize * 1.5
                        font.weight: Font.Bold
                    }
                    RowLayout {
                        spacing: Kirigami.Units.smallSpacing
                        // Claude logo small
                        Image {
                            source: Qt.resolvedUrl("../icons/claude-logo.svg")
                            Layout.preferredWidth: 12
                            Layout.preferredHeight: 12
                            sourceSize: Qt.size(12, 12)
                            fillMode: Image.PreserveAspectFit
                        }
                        PlasmaComponents3.Label {
                            text: root.usageData.rateLimits?.plan ?? "Max (20x)"
                            font.pixelSize: Kirigami.Theme.defaultFont.pixelSize * 0.8
                            color: root.claudeAmber
                            opacity: 0.8
                        }
                        Rectangle {
                            width: 4; height: 4; radius: 2
                            color: Kirigami.Theme.textColor; opacity: 0.2
                        }
                        PlasmaComponents3.Label {
                            text: {
                                var src = root.usageData.rateLimits?.source ?? "";
                                return src === "api" ? "Live" : "Offline";
                            }
                            font.pixelSize: Kirigami.Theme.defaultFont.pixelSize * 0.75
                            color: root.usageData.rateLimits?.source === "api" ? root.greenAccent : Kirigami.Theme.textColor
                            opacity: 0.6
                        }
                    }
                }

                Item { Layout.fillWidth: true }

                PlasmaComponents3.ToolButton {
                    icon.name: "view-refresh"
                    onClicked: dataLoader.readData()
                    PlasmaComponents3.ToolTip { text: "Refresh" }
                }
            }

            // ══════════════════════════════════
            // ── Session Limit (HERO CARD) ──
            // ══════════════════════════════════
            Rectangle {
                Layout.fillWidth: true
                implicitHeight: sessionInner.implicitHeight + Kirigami.Units.largeSpacing * 2
                radius: 12
                color: root.cardBg
                border.width: 2
                border.color: {
                    var p = root.usageData.rateLimits?.session?.percentUsed ?? 0;
                    if (p > 80) return Qt.rgba(redAlert.r, redAlert.g, redAlert.b, 0.6);
                    if (p > 50) return Qt.rgba(claudeAmberLight.r, claudeAmberLight.g, claudeAmberLight.b, 0.5);
                    return Qt.rgba(claudeAmber.r, claudeAmber.g, claudeAmber.b, 0.35);
                }

                ColumnLayout {
                    id: sessionInner
                    anchors.fill: parent
                    anchors.margins: Kirigami.Units.largeSpacing
                    spacing: 6

                    RowLayout {
                        Layout.fillWidth: true
                        PlasmaComponents3.Label {
                            text: "Current session"
                            font.pixelSize: Kirigami.Theme.defaultFont.pixelSize * 0.9
                            font.weight: Font.DemiBold
                            opacity: 0.7
                        }
                        Item { Layout.fillWidth: true }
                        PlasmaComponents3.Label {
                            property int mins: root.usageData.rateLimits?.session?.resetsInMinutes ?? 0
                            text: mins > 60 ? "Resets in " + Math.floor(mins/60) + "h " + (mins%60) + "m"
                                 : mins > 0 ? "Resets in " + mins + "m" : "Rolling 5h"
                            font.pixelSize: Kirigami.Theme.defaultFont.pixelSize * 0.8
                            opacity: 0.4
                        }
                    }

                    // Big percentage number
                    PlasmaComponents3.Label {
                        property real pct: root.usageData.rateLimits?.session?.percentUsed ?? 0
                        text: Math.round(pct) + "%"
                        font.pixelSize: Kirigami.Theme.defaultFont.pixelSize * 3.2
                        font.weight: Font.Bold
                        color: limitColor(pct)
                        Layout.alignment: Qt.AlignHCenter
                    }

                    // Progress bar (thick, rounded)
                    Rectangle {
                        Layout.fillWidth: true
                        height: 12; radius: 6
                        color: root.subtleBorder

                        Rectangle {
                            property real pct: root.usageData.rateLimits?.session?.percentUsed ?? 0
                            width: parent.width * Math.min(1, pct / 100)
                            height: parent.height; radius: 6
                            color: barFill(pct, root.claudeAmber)

                            // Subtle shine effect
                            Rectangle {
                                anchors.top: parent.top
                                width: parent.width; height: parent.height / 2
                                radius: 6
                                color: "white"; opacity: 0.08
                            }

                            Behavior on width { NumberAnimation { duration: 700; easing.type: Easing.OutCubic } }
                        }
                    }
                }
            }

            // ══════════════════════════════════
            // ── Weekly Limits Card ──
            // ══════════════════════════════════
            Rectangle {
                Layout.fillWidth: true
                implicitHeight: weeklyCol.implicitHeight + Kirigami.Units.mediumSpacing * 2
                radius: 10
                color: root.cardBg

                ColumnLayout {
                    id: weeklyCol
                    anchors.fill: parent
                    anchors.margins: Kirigami.Units.mediumSpacing
                    spacing: Kirigami.Units.mediumSpacing

                    PlasmaComponents3.Label {
                        text: "Weekly limits"
                        font.pixelSize: Kirigami.Theme.defaultFont.pixelSize * 0.85
                        font.weight: Font.DemiBold
                        opacity: 0.5
                    }

                    // All models row
                    ColumnLayout {
                        Layout.fillWidth: true
                        spacing: 4

                        RowLayout {
                            Layout.fillWidth: true
                            Rectangle { width: 8; height: 8; radius: 4; color: root.blueAccent }
                            PlasmaComponents3.Label {
                                text: "All models"
                                font.pixelSize: Kirigami.Theme.defaultFont.pixelSize * 0.9
                            }
                            Item { Layout.fillWidth: true }
                            PlasmaComponents3.Label {
                                visible: (root.usageData.rateLimits?.weeklyAll?.resetsLabel ?? "") !== ""
                                text: "Resets " + (root.usageData.rateLimits?.weeklyAll?.resetsLabel ?? "")
                                font.pixelSize: Kirigami.Theme.defaultFont.pixelSize * 0.7
                                opacity: 0.35
                            }
                            PlasmaComponents3.Label {
                                property real pct: root.usageData.rateLimits?.weeklyAll?.percentUsed ?? 0
                                text: Math.round(pct) + "%"
                                font.pixelSize: Kirigami.Theme.defaultFont.pixelSize * 1.1
                                font.weight: Font.Bold
                                color: limitColor(pct)
                            }
                        }

                        Rectangle {
                            Layout.fillWidth: true; height: 6; radius: 3
                            color: root.subtleBorder
                            Rectangle {
                                property real pct: root.usageData.rateLimits?.weeklyAll?.percentUsed ?? 0
                                width: parent.width * Math.min(1, pct / 100)
                                height: parent.height; radius: 3
                                color: barFill(pct, root.blueAccent)
                                Behavior on width { NumberAnimation { duration: 600; easing.type: Easing.OutCubic } }
                            }
                        }
                    }

                    // Sonnet only row
                    ColumnLayout {
                        Layout.fillWidth: true
                        spacing: 4

                        RowLayout {
                            Layout.fillWidth: true
                            Rectangle { width: 8; height: 8; radius: 4; color: root.greenAccent }
                            PlasmaComponents3.Label {
                                text: "Sonnet only"
                                font.pixelSize: Kirigami.Theme.defaultFont.pixelSize * 0.9
                            }
                            Item { Layout.fillWidth: true }
                            PlasmaComponents3.Label {
                                visible: (root.usageData.rateLimits?.weeklySonnet?.resetsLabel ?? "") !== ""
                                text: "Resets " + (root.usageData.rateLimits?.weeklySonnet?.resetsLabel ?? "")
                                font.pixelSize: Kirigami.Theme.defaultFont.pixelSize * 0.7
                                opacity: 0.35
                            }
                            PlasmaComponents3.Label {
                                property real pct: root.usageData.rateLimits?.weeklySonnet?.percentUsed ?? 0
                                text: Math.round(pct) + "%"
                                font.pixelSize: Kirigami.Theme.defaultFont.pixelSize * 1.1
                                font.weight: Font.Bold
                                color: limitColor(pct)
                            }
                        }

                        Rectangle {
                            Layout.fillWidth: true; height: 6; radius: 3
                            color: root.subtleBorder
                            Rectangle {
                                property real pct: root.usageData.rateLimits?.weeklySonnet?.percentUsed ?? 0
                                width: parent.width * Math.min(1, pct / 100)
                                height: parent.height; radius: 3
                                color: barFill(pct, root.greenAccent)
                                Behavior on width { NumberAnimation { duration: 600; easing.type: Easing.OutCubic } }
                            }
                        }
                    }
                }
            }

            // ══════════════════════════════════
            // ── Balance Card ──
            // ══════════════════════════════════
            Rectangle {
                Layout.fillWidth: true
                visible: root.usageData.rateLimits?.credits != null
                implicitHeight: balanceRow.implicitHeight + Kirigami.Units.mediumSpacing * 2
                radius: 10
                color: root.cardBg

                RowLayout {
                    id: balanceRow
                    anchors.fill: parent
                    anchors.margins: Kirigami.Units.mediumSpacing
                    spacing: Kirigami.Units.smallSpacing

                    Kirigami.Icon {
                        source: "wallet-open"
                        Layout.preferredWidth: Kirigami.Units.iconSizes.smallMedium
                        Layout.preferredHeight: Kirigami.Units.iconSizes.smallMedium
                        color: root.claudeAmber
                        opacity: 0.6
                    }

                    PlasmaComponents3.Label {
                        text: "Balance"
                        font.pixelSize: Kirigami.Theme.defaultFont.pixelSize * 0.9
                        opacity: 0.5
                    }
                    Item { Layout.fillWidth: true }
                    PlasmaComponents3.Label {
                        text: {
                            var c = root.usageData.rateLimits?.credits ?? {};
                            var amount = c.amount ?? 0;
                            var currency = c.currency ?? "USD";
                            if (currency === "BRL") return "R$ " + amount.toLocaleString(Qt.locale(), 'f', 2);
                            return "$ " + amount.toLocaleString(Qt.locale(), 'f', 2);
                        }
                        font.pixelSize: Kirigami.Theme.defaultFont.pixelSize * 1.2
                        font.weight: Font.Bold
                        color: root.claudeAmber
                    }
                }
            }

            // ══════════════════════════════════
            // ── Service Health Card ──
            // ══════════════════════════════════
            Rectangle {
                Layout.fillWidth: true
                visible: root.usageData.serviceStatus != null
                radius: 10
                color: {
                    var ind = root.usageData.serviceStatus?.indicator ?? "none";
                    if (ind === "none") return root.cardBg;
                    if (ind === "minor") return Qt.rgba(0.984, 0.620, 0.086, 0.10);
                    return Qt.rgba(0.937, 0.267, 0.267, 0.10);
                }
                border.width: 1
                border.color: {
                    var ind = root.usageData.serviceStatus?.indicator ?? "none";
                    if (ind === "none") return root.subtleBorder;
                    if (ind === "minor") return Qt.rgba(0.984, 0.620, 0.086, 0.40);
                    return Qt.rgba(0.937, 0.267, 0.267, 0.40);
                }
                implicitHeight: serviceHealthCol.implicitHeight + Kirigami.Units.mediumSpacing * 2

                ColumnLayout {
                    id: serviceHealthCol
                    anchors.fill: parent
                    anchors.margins: Kirigami.Units.mediumSpacing
                    spacing: 6

                    // Overall status row
                    RowLayout {
                        Layout.fillWidth: true
                        spacing: 6

                        // Pulsing dot
                        Rectangle {
                            id: healthDot
                            property string ind: root.usageData.serviceStatus?.indicator ?? "none"
                            width: 10; height: 10; radius: 5
                            color: statusColor(ind)

                            SequentialAnimation on opacity {
                                running: healthDot.ind !== "none"
                                loops: Animation.Infinite
                                NumberAnimation { to: 0.3; duration: 900; easing.type: Easing.InOutSine }
                                NumberAnimation { to: 1.0; duration: 900; easing.type: Easing.InOutSine }
                            }
                        }

                        PlasmaComponents3.Label {
                            text: "Service Health"
                            font.pixelSize: Kirigami.Theme.defaultFont.pixelSize * 0.88
                            font.weight: Font.DemiBold
                            opacity: 0.65
                        }

                        Item { Layout.fillWidth: true }

                        // Status pill badge
                        Rectangle {
                            property string ind: root.usageData.serviceStatus?.indicator ?? "none"
                            radius: height / 2
                            color: {
                                var c = statusColor(ind);
                                return Qt.rgba(c.r, c.g, c.b, 0.20);
                            }
                            border.width: 1
                            border.color: {
                                var c = statusColor(ind);
                                return Qt.rgba(c.r, c.g, c.b, 0.55);
                            }
                            implicitWidth: _statusBadge.implicitWidth + 18
                            implicitHeight: _statusBadge.implicitHeight + 8

                            PlasmaComponents3.Label {
                                id: _statusBadge
                                anchors.centerIn: parent
                                text: {
                                    var ind = root.usageData.serviceStatus?.indicator ?? "none";
                                    if (ind === "none")     return "Healthy";
                                    if (ind === "minor")    return "Degraded";
                                    if (ind === "major")    return "Major Outage";
                                    if (ind === "critical") return "Critical Outage";
                                    return "Unknown";
                                }
                                font.pixelSize: Kirigami.Theme.defaultFont.pixelSize * 0.88
                                font.weight: Font.Bold
                                color: statusColor(root.usageData.serviceStatus?.indicator ?? "none")
                            }
                        }
                    }

                    // Component dots row
                    RowLayout {
                        Layout.fillWidth: true
                        spacing: Kirigami.Units.smallSpacing

                        Repeater {
                            model: root.usageData.serviceStatus?.components ?? []
                            RowLayout {
                                spacing: 3
                                Rectangle {
                                    width: 6; height: 6; radius: 3
                                    color: componentStatusColor(modelData.status ?? "")
                                }
                                PlasmaComponents3.Label {
                                    text: modelData.name ?? ""
                                    font.pixelSize: Kirigami.Theme.defaultFont.pixelSize * 0.72
                                    opacity: 0.55
                                }
                            }
                        }

                        Item { Layout.fillWidth: true }
                    }

                    // DownDetector link (crowd-sourced early warning)
                    RowLayout {
                        Layout.fillWidth: true
                        spacing: 4

                        Kirigami.Icon {
                            source: "globe"
                            Layout.preferredWidth: 10; Layout.preferredHeight: 10
                            opacity: 0.35
                        }

                        PlasmaComponents3.Label {
                            text: "User reports:"
                            font.pixelSize: Kirigami.Theme.defaultFont.pixelSize * 0.72
                            opacity: 0.35
                        }

                        Item { Layout.fillWidth: true }

                        PlasmaComponents3.ToolButton {
                            text: "DownDetector ↗"
                            font.pixelSize: Kirigami.Theme.defaultFont.pixelSize * 0.72
                            opacity: 0.55
                            flat: true
                            padding: 0
                            onClicked: Qt.openUrlExternally("https://downdetector.com/status/claude-ai/")
                        }
                    }

                    // Active incident details
                    Repeater {
                        model: root.activeIncidents
                        ColumnLayout {
                            Layout.fillWidth: true
                            spacing: 2

                            PlasmaComponents3.Label {
                                Layout.fillWidth: true
                                text: modelData.name ?? ""
                                font.pixelSize: Kirigami.Theme.defaultFont.pixelSize * 0.78
                                font.weight: Font.DemiBold
                                color: root.redAlert
                                wrapMode: Text.WordWrap
                                maximumLineCount: 2
                                elide: Text.ElideRight
                            }

                            PlasmaComponents3.Label {
                                Layout.fillWidth: true
                                visible: (modelData.latest_update ?? "") !== ""
                                text: modelData.latest_update ?? ""
                                font.pixelSize: Kirigami.Theme.defaultFont.pixelSize * 0.73
                                opacity: 0.50
                                wrapMode: Text.WordWrap
                                maximumLineCount: 2
                                elide: Text.ElideRight
                            }
                        }
                    }
                }
            }

            // ══════════════════════════════════
            // ── Intelligence / Dumbness Card ──
            // ══════════════════════════════════
            Rectangle {
                Layout.fillWidth: true
                visible: root.dumbScore > 0
                radius: 10
                color: {
                    if (root.dumbScore >= 75) return Qt.rgba(0.937, 0.267, 0.267, 0.12);
                    if (root.dumbScore >= 50) return Qt.rgba(0.976, 0.451, 0.086, 0.10);
                    if (root.dumbScore >= 25) return Qt.rgba(0.961, 0.620, 0.043, 0.10);
                    return root.cardBg;
                }
                border.width: 1
                border.color: root.subtleBorder
                implicitHeight: dumbCol.implicitHeight + Kirigami.Units.mediumSpacing * 2

                ColumnLayout {
                    id: dumbCol
                    anchors.fill: parent
                    anchors.margins: Kirigami.Units.mediumSpacing
                    spacing: 4

                    RowLayout {
                        Layout.fillWidth: true
                        spacing: 6

                        PlasmaComponents3.Label {
                            text: {
                                var lvl = root.dumbLevel;
                                if (lvl === "braindead") return "🧠 Braindead";
                                if (lvl === "dumb") return "🐴 Dumb";
                                if (lvl === "slow") return "🐌 Slow";
                                return "🤔 Hmm";
                            }
                            font.pixelSize: Kirigami.Theme.defaultFont.pixelSize * 0.9
                            font.weight: Font.Bold
                        }

                        Item { Layout.fillWidth: true }

                        // Score badge
                        Rectangle {
                            radius: height / 2
                            color: {
                                if (root.dumbScore >= 75) return Qt.rgba(0.937, 0.267, 0.267, 0.25);
                                if (root.dumbScore >= 50) return Qt.rgba(0.976, 0.451, 0.086, 0.25);
                                return Qt.rgba(0.961, 0.620, 0.043, 0.25);
                            }
                            implicitWidth: _dumbLabel.implicitWidth + 14
                            implicitHeight: _dumbLabel.implicitHeight + 6

                            PlasmaComponents3.Label {
                                id: _dumbLabel
                                anchors.centerIn: parent
                                text: root.dumbScore + "/100"
                                font.pixelSize: Kirigami.Theme.defaultFont.pixelSize * 0.78
                                font.weight: Font.Bold
                                color: {
                                    if (root.dumbScore >= 75) return root.redAlert;
                                    if (root.dumbScore >= 50) return "#F97316";
                                    return root.claudeAmberLight;
                                }
                            }
                        }
                    }

                    // Reasons list
                    Repeater {
                        model: root.usageData.dumbness?.reasons ?? []
                        PlasmaComponents3.Label {
                            Layout.fillWidth: true
                            text: "  • " + modelData
                            font.pixelSize: Kirigami.Theme.defaultFont.pixelSize * 0.72
                            opacity: 0.55
                        }
                    }

                    // Adaptive thinking workaround tip
                    PlasmaComponents3.Label {
                        Layout.fillWidth: true
                        visible: !(root.usageData.adaptiveThinking?.adaptive_thinking ?? true)
                        text: "Tip: Adaptive Thinking is OFF in settings.json"
                        font.pixelSize: Kirigami.Theme.defaultFont.pixelSize * 0.72
                        font.italic: true
                        opacity: 0.45
                        wrapMode: Text.WordWrap
                    }
                }
            }

            // ══════════════════════════════════
            // ── Burn Rate & Errors Card ──
            // ══════════════════════════════════
            Rectangle {
                Layout.fillWidth: true
                radius: 10
                color: root.cardBg
                implicitHeight: burnCol.implicitHeight + Kirigami.Units.mediumSpacing * 2

                ColumnLayout {
                    id: burnCol
                    anchors.fill: parent
                    anchors.margins: Kirigami.Units.mediumSpacing
                    spacing: 6

                    PlasmaComponents3.Label {
                        text: "Activity"
                        font.pixelSize: Kirigami.Theme.defaultFont.pixelSize * 0.8
                        font.weight: Font.DemiBold
                        opacity: 0.5
                    }

                    // Burn rate row
                    RowLayout {
                        Layout.fillWidth: true
                        spacing: 4

                        Kirigami.Icon {
                            source: "speedometer"
                            Layout.preferredWidth: 14; Layout.preferredHeight: 14
                            opacity: 0.5
                        }

                        PlasmaComponents3.Label {
                            text: "Burn rate"
                            font.pixelSize: Kirigami.Theme.defaultFont.pixelSize * 0.82
                            opacity: 0.6
                        }

                        Item { Layout.fillWidth: true }

                        PlasmaComponents3.Label {
                            property int rate: root.usageData.burnRate?.output_per_hour ?? 0
                            text: {
                                if (rate >= 1e6) return (rate / 1e6).toFixed(1) + "M/h";
                                if (rate >= 1e3) return (rate / 1e3).toFixed(0) + "K/h";
                                return rate + "/h";
                            }
                            font.pixelSize: Kirigami.Theme.defaultFont.pixelSize * 0.9
                            font.weight: Font.Bold
                            color: rate > 500000 ? root.claudeAmberLight : Kirigami.Theme.textColor
                        }
                    }

                    // Error rate row
                    RowLayout {
                        Layout.fillWidth: true
                        spacing: 4

                        Kirigami.Icon {
                            source: "dialog-warning-symbolic"
                            Layout.preferredWidth: 14; Layout.preferredHeight: 14
                            opacity: 0.5
                        }

                        PlasmaComponents3.Label {
                            text: "Errors (2h)"
                            font.pixelSize: Kirigami.Theme.defaultFont.pixelSize * 0.82
                            opacity: 0.6
                        }

                        Item { Layout.fillWidth: true }

                        PlasmaComponents3.Label {
                            property int errs: root.usageData.errorRate?.total ?? 0
                            text: errs > 0 ? errs + " errors" : "None"
                            font.pixelSize: Kirigami.Theme.defaultFont.pixelSize * 0.85
                            font.weight: Font.Bold
                            color: errs > 5 ? root.redAlert : errs > 0 ? root.claudeAmberLight : root.greenAccent
                        }
                    }

                    // Adaptive thinking status row
                    RowLayout {
                        Layout.fillWidth: true
                        spacing: 4

                        Kirigami.Icon {
                            source: "preferences-system"
                            Layout.preferredWidth: 14; Layout.preferredHeight: 14
                            opacity: 0.5
                        }

                        PlasmaComponents3.Label {
                            text: "Adaptive Thinking"
                            font.pixelSize: Kirigami.Theme.defaultFont.pixelSize * 0.82
                            opacity: 0.6
                        }

                        Item { Layout.fillWidth: true }

                        PlasmaComponents3.Label {
                            property bool on: root.usageData.adaptiveThinking?.adaptive_thinking ?? true
                            text: on ? "ON" : "OFF"
                            font.pixelSize: Kirigami.Theme.defaultFont.pixelSize * 0.85
                            font.weight: Font.Bold
                            color: on ? root.greenAccent : root.redAlert
                        }
                    }
                }
            }

            // ══════════════════════════════════
            // ── Quick Actions ──
            // ══════════════════════════════════
            RowLayout {
                Layout.fillWidth: true
                spacing: Kirigami.Units.smallSpacing

                PlasmaComponents3.Button {
                    Layout.fillWidth: true
                    text: "claude.ai"
                    icon.name: "internet-web-browser"
                    font.pixelSize: Kirigami.Theme.defaultFont.pixelSize * 0.78
                    onClicked: Qt.openUrlExternally("https://claude.ai")
                }

                PlasmaComponents3.Button {
                    Layout.fillWidth: true
                    text: "Status"
                    icon.name: "network-connect"
                    font.pixelSize: Kirigami.Theme.defaultFont.pixelSize * 0.78
                    onClicked: Qt.openUrlExternally("https://status.claude.com")
                }

                PlasmaComponents3.Button {
                    Layout.fillWidth: true
                    text: "DownDetector"
                    icon.name: "globe"
                    font.pixelSize: Kirigami.Theme.defaultFont.pixelSize * 0.78
                    onClicked: Qt.openUrlExternally("https://downdetector.com/status/claude-ai/")
                }
            }

            // ══════════════════════════════════
            // ── 7-Day Activity Chart ──
            // ══════════════════════════════════
            Rectangle {
                Layout.fillWidth: true
                implicitHeight: chartCol.implicitHeight + Kirigami.Units.mediumSpacing * 2
                radius: 10
                color: root.cardBg

                ColumnLayout {
                    id: chartCol
                    anchors.fill: parent
                    anchors.margins: Kirigami.Units.mediumSpacing
                    spacing: 4

                    PlasmaComponents3.Label {
                        text: "7-day activity"
                        font.pixelSize: Kirigami.Theme.defaultFont.pixelSize * 0.8
                        opacity: 0.4
                    }

                    Item {
                        Layout.fillWidth: true
                        Layout.preferredHeight: Kirigami.Units.gridUnit * 3.5

                        Canvas {
                            id: trendChart
                            anchors.fill: parent
                            property var chartData: root.usageData.trend7d ?? []
                            onChartDataChanged: requestPaint()
                            onWidthChanged: requestPaint()
                            onHeightChanged: requestPaint()

                            onPaint: {
                                var ctx = getContext("2d");
                                ctx.clearRect(0, 0, width, height);
                                var data = chartData;
                                if (!data || data.length === 0) return;

                                var maxT = 1;
                                for (var k = 0; k < data.length; k++)
                                    if ((data[k].tokens || 0) > maxT) maxT = data[k].tokens;

                                var bw = (width - 12) / data.length;
                                var pad = 3;
                                var ch = height - 14;

                                for (var i = 0; i < data.length; i++) {
                                    var x = 6 + i * bw + pad / 2;
                                    var barH = Math.max(2, (data[i].tokens / maxT) * ch);
                                    var y = ch - barH;
                                    var w = bw - pad;
                                    var isLast = (i === data.length - 1);

                                    // Gradient-like effect: brighter for today
                                    var alpha = isLast ? 0.85 : 0.2 + (i / data.length) * 0.2;
                                    ctx.fillStyle = Qt.rgba(0.851, 0.467, 0.024, alpha);

                                    var r = Math.min(4, w / 2);
                                    ctx.beginPath();
                                    ctx.moveTo(x + r, y);
                                    ctx.arcTo(x + w, y, x + w, y + barH, r);
                                    ctx.lineTo(x + w, ch);
                                    ctx.lineTo(x, ch);
                                    ctx.arcTo(x, y, x + r, y, r);
                                    ctx.closePath();
                                    ctx.fill();

                                    // Day label
                                    ctx.fillStyle = Kirigami.Theme.textColor.toString();
                                    ctx.globalAlpha = isLast ? 0.8 : 0.35;
                                    ctx.font = (isLast ? "bold " : "") + "8px sans-serif";
                                    ctx.textAlign = "center";
                                    ctx.fillText(data[i].label || "", x + w / 2, height - 1);
                                    ctx.globalAlpha = 1.0;
                                }
                            }
                        }
                    }
                }
            }

            // ══════════════════════════════════
            // ── Footer ──
            // ══════════════════════════════════
            RowLayout {
                Layout.fillWidth: true
                spacing: Kirigami.Units.smallSpacing

                Image {
                    source: Qt.resolvedUrl("../icons/claude-logo.svg")
                    Layout.preferredWidth: 10
                    Layout.preferredHeight: 10
                    sourceSize: Qt.size(10, 10)
                    fillMode: Image.PreserveAspectFit
                    opacity: 0.4
                }

                PlasmaComponents3.Label {
                    text: (root.usageData.lifetime?.totalSessions ?? 0) + " sessions"
                    font.pixelSize: Kirigami.Theme.defaultFont.pixelSize * 0.75
                    opacity: 0.3
                }

                Rectangle { width: 3; height: 3; radius: 1.5; color: Kirigami.Theme.textColor; opacity: 0.15 }

                PlasmaComponents3.Label {
                    text: {
                        var s = root.usageData.lifetime?.firstSession ?? "";
                        if (!s) return "";
                        return "since " + new Date(s).toLocaleDateString(Qt.locale(), "MMM yyyy");
                    }
                    font.pixelSize: Kirigami.Theme.defaultFont.pixelSize * 0.75
                    opacity: 0.3
                }

                Item { Layout.fillWidth: true }

                PlasmaComponents3.Label {
                    text: "Anthropic"
                    font.pixelSize: Kirigami.Theme.defaultFont.pixelSize * 0.7
                    font.weight: Font.DemiBold
                    opacity: 0.2
                }
            }
        }
        } // Flickable
    }
}
