import Foundation
import CoreGraphics
import CoreVideo
import AppKit
import OSLog

/*
 File: refresh_rate.swift
 Purpose: Measure and report the display refresh characteristics for the built‑in display.

 Table of Contents
 1. Constants & Types            (RRConstants, RRKeys)
 2. Logging                      (logger)
 3. Utility Functions            (hz(from:), hzAny(_:), builtinDisplayID(), refreshFromDisplayMode(_:))
 4. CVDisplayLink Sampling       (Sampler, outputCallback)
 5. Public API                   (sampleRates(for:duration:))
 6. Main                         (argument/env parsing, JSON output)
 */

// MARK: - 1. Constants & Types
private enum RRConstants {
    static let defaultSampleSeconds: Double = 1.0
    static let defaultMaxSamples: Int = 600
    static let subsystem: String = "com.machealthcheckup"
    static let category: String  = "refresh_rate"
    static let nsScreenNumberKey = "NSScreenNumber"
    static let envSampleSecs = "SAMPLE_SECS"
    static let envMaxSamples = "SAMPLE_MAX_SAMPLES"
}

private enum RRKeys {
    static let builtinHzMode      = "builtin_hz_mode"
    static let builtinHzNominal   = "builtin_hz_nominal"
    static let builtinHzActual    = "builtin_hz_actual"
    static let builtinSampleCount = "builtin_sample_count"
    static let builtinHzMin       = "builtin_hz_min"
    static let builtinHzMax       = "builtin_hz_max"
    static let builtinHzMean      = "builtin_hz_mean"
    static let builtinHzMedian    = "builtin_hz_median"
    static let builtinMaxFPS      = "builtin_max_fps"
    static let builtinDisplayID   = "builtin_display_id"
    static let builtinAggregate  = "builtin"
    static let error              = "error"
    static let message            = "message"
    static let json               = "json"
}

// MARK: - 2. Logging
private let logger = Logger(subsystem: RRConstants.subsystem, category: RRConstants.category)

// MARK: - 3.1 Types for statistics & nested JSON (future-proof)
private struct HzPair: Codable {
    let nominal: Double
    let actual: Double
    enum CodingKeys: String, CodingKey {
        case nominal = "nominal_hz"
        case actual  = "actual_hz"
    }
}

private struct FrameStats: Codable {
    let count: Int
    let min: Double
    let max: Double
    let mean: Double
    let median: Double
}

private struct BuiltinAggregate: Codable {
    let displayID: UInt32
    let modeHz: Double?
    let cv: HzPair
    let stats: FrameStats?
    let maxFPS: Int?
}

// MARK: - 3. Utility Functions
/// Convert a `CVTime` period to frequency in Hertz.
/// - Parameter t: A CoreVideo time value.
/// - Returns: Frequency in Hz, or 0.0 if `timeValue` is zero.
@inline(__always)
func hz(from t: CVTime) -> Double {
    guard t.timeValue != 0 else { return 0.0 }
    return Double(t.timeScale) / Double(t.timeValue)
}

/// Convert either a `CVTime` or seconds-as-`Double` to Hertz.
/// - Parameter v: `CVTime` or `Double` seconds. Any other type yields 0.0.
/// - Returns: Frequency in Hz.
@inline(__always)
func hzAny(_ v: Any) -> Double {
    if let t = v as? CVTime { return hz(from: t) }
    if let d = v as? Double { return d > 0 ? 1.0 / d : 0.0 }
    return 0.0
}

/// Resolve the built‑in display's `CGDirectDisplayID`.
/// Tries CoreGraphics first, then falls back to `NSScreen` mapping.
/// - Returns: Built‑in display ID if present.
func builtinDisplayID() -> CGDirectDisplayID? {
    var count: UInt32 = 0
    CGGetActiveDisplayList(0, nil, &count)
    var ids = [CGDirectDisplayID](repeating: 0, count: Int(count))
    CGGetActiveDisplayList(count, &ids, &count)
    if let id = ids.first(where: { CGDisplayIsBuiltin($0) != 0 }) {
        return id
    }
    for screen in NSScreen.screens {
        if let num = screen.deviceDescription[NSDeviceDescriptionKey(RRConstants.nsScreenNumberKey)] as? NSNumber {
            let id = CGDirectDisplayID(num.uint32Value)
            if CGDisplayIsBuiltin(id) != 0 { return id }
        }
    }
    return nil
}

/// Fetch the refresh rate directly from the current `CGDisplayMode` if available.
/// - Parameter id: Target display ID.
/// - Returns: Refresh rate in Hz when reported (> 0), otherwise `nil`.
func refreshFromDisplayMode(_ id: CGDirectDisplayID) -> Double? {
    guard let mode = CGDisplayCopyDisplayMode(id) else { return nil }
    let rr = mode.refreshRate
    return rr > 0 ? rr : nil
}

/// Compute statistics (min/max/mean/median in Hz) from an array of frame periods in seconds.
/// - Parameter periods: Frame durations in seconds.
/// - Returns: `FrameStats` when at least one period exists; otherwise `nil`.
@inline(__always)
private func computeStats(periods: [Double]) -> FrameStats? {
    guard !periods.isEmpty else { return nil }
    let hzs = periods.map { $0 > 0 ? 1.0 / $0 : 0.0 }.sorted()
    guard let minHz = hzs.first, let maxHz = hzs.last else { return nil }
    let meanHz = hzs.reduce(0, +) / Double(hzs.count)
    let mid = hzs.count / 2
    let medianHz: Double = (hzs.count % 2 == 0) ? (hzs[mid - 1] + hzs[mid]) / 2.0 : hzs[mid]
    return FrameStats(count: hzs.count, min: minHz, max: maxHz, mean: meanHz, median: medianHz)
}

/// Extract nominal/actual refresh periods from a display link and convert to Hz.
@inline(__always)
private func hzPair(from link: CVDisplayLink) -> HzPair {
    let nominalAny: Any = CVDisplayLinkGetNominalOutputVideoRefreshPeriod(link) as Any
    let actualAny: Any  = CVDisplayLinkGetActualOutputVideoRefreshPeriod(link) as Any
    return HzPair(nominal: hzAny(nominalAny), actual: hzAny(actualAny))
}


/// Find NSScreen matching a display id.
private func screen(for display: CGDirectDisplayID) -> NSScreen? {
    for screen in NSScreen.screens {
        if let num = screen.deviceDescription[NSDeviceDescriptionKey(RRConstants.nsScreenNumberKey)] as? NSNumber,
           CGDirectDisplayID(num.uint32Value) == display { return screen }
    }
    return nil
}

/// Parse a Double from env using the provided key, returning nil if missing/invalid/non-positive when `positiveOnly` is true.
private func envDouble(_ env: [String: String], key: String, positiveOnly: Bool = true) -> Double? {
    guard let s = env[key], let v = Double(s) else { return nil }
    if positiveOnly && v <= 0 { return nil }
    return v
}

/// Parse an Int from env using the provided key.
private func envInt(_ env: [String: String], key: String, positiveOnly: Bool = true) -> Int? {
    guard let s = env[key], let v = Int(s) else { return nil }
    if positiveOnly && v <= 0 { return nil }
    return v
}

// MARK: - 4. CVDisplayLink Sampling
/// Accumulates frame periods reported by a `CVDisplayLink` for later statistics.
final class Sampler {
    var periods: [Double] = []               // seconds per frame
    var lastVideoTime: Int64? = nil
    var videoTimeScale: Int32 = 0
    var start: CFAbsoluteTime = CFAbsoluteTimeGetCurrent()
    let maxSamples: Int
    let targetSamples: Int        // stop after this many samples
    let runLoop: CFRunLoop        // run‑loop to stop when done

    init(duration: Double,
         maxSamples: Int = RRConstants.defaultMaxSamples,
         targetSamples: Int = 5,
         runLoop: CFRunLoop = CFRunLoopGetCurrent()) {
        self.maxSamples = maxSamples
        self.targetSamples = targetSamples
        self.runLoop = runLoop
        periods.reserveCapacity(maxSamples)
    }

    func add(_ seconds: Double, vt: Int64, scale: Int32) {
        if periods.count < maxSamples { periods.append(seconds) }
        videoTimeScale = scale
    }
}

func outputCallback(link: CVDisplayLink,
                    inNow: UnsafePointer<CVTimeStamp>,
                    inOutputTime: UnsafePointer<CVTimeStamp>,
                    flagsIn: CVOptionFlags,
                    flagsOut: UnsafeMutablePointer<CVOptionFlags>,
                    displayLinkContext: UnsafeMutableRawPointer?) -> CVReturn {
    guard let ctx = displayLinkContext else { return kCVReturnSuccess }
    let sampler = Unmanaged<Sampler>.fromOpaque(ctx).takeUnretainedValue()

    // Compute period using videoTime ticks
    let vt = inOutputTime.pointee.videoTime
    let scale = inOutputTime.pointee.videoTimeScale
    if sampler.lastVideoTime == nil {
        sampler.lastVideoTime = vt
        return kCVReturnSuccess
    }
    let last = sampler.lastVideoTime!
    let deltaTicks = vt - last
    sampler.lastVideoTime = vt
    if deltaTicks > 0 && scale > 0 {
        let seconds = Double(deltaTicks) / Double(scale)
        sampler.add(seconds, vt: vt, scale: scale)
        // Early exit once we have enough samples.
        if sampler.periods.count >= sampler.targetSamples {
            CVDisplayLinkStop(link)
            CFRunLoopStop(sampler.runLoop)
        }
    }

    // Stop condition hint: we can't stop the link from inside the callback cleanly; the main thread will stop it.
    return kCVReturnSuccess
}

// MARK: - 5. Public API
func sampleRates(for display: CGDirectDisplayID, duration: Double) -> [String: Any] {
    var result: [String: Any] = [:]

    // Prefer CGDisplayMode if available
    if let modeHz = refreshFromDisplayMode(display) { result[RRKeys.builtinHzMode] = modeHz }

    // Create link
    var link: CVDisplayLink?
    let rc = CVDisplayLinkCreateWithCGDisplay(display, &link)
    guard rc == kCVReturnSuccess, let link else {
        logger.error("CVDisplayLinkCreateWithCGDisplay failed: rc=\(rc, format: .decimal)")
        return result
    }

    let env = ProcessInfo.processInfo.environment
    let maxSamples = envInt(env, key: RRConstants.envMaxSamples) ?? RRConstants.defaultMaxSamples
    let sampler = Sampler(duration: duration,
                          maxSamples: maxSamples,
                          targetSamples: 5,           // collect just 5 frames
                          runLoop: CFRunLoopGetCurrent())

    let ctx = Unmanaged.passUnretained(sampler).toOpaque()
    CVDisplayLinkSetOutputCallback(link, outputCallback, ctx)

    let startRC = CVDisplayLinkStart(link)
    if startRC != kCVReturnSuccess {
        logger.error("CVDisplayLinkStart failed: rc=\(startRC, format: .decimal)")
        return result
    }

    // Run until the callback gathers `targetSamples` or the timeout timer fires.
    CFRunLoopRun()

    CVDisplayLinkStop(link)

    let pair = hzPair(from: link)
    result[RRKeys.builtinHzNominal] = pair.nominal
    result[RRKeys.builtinHzActual]  = pair.actual

    let samples = sampler.periods
    result[RRKeys.builtinSampleCount] = samples.count
    if let stats = computeStats(periods: samples) {
        result[RRKeys.builtinHzMin] = stats.min
        result[RRKeys.builtinHzMax] = stats.max
        result[RRKeys.builtinHzMean] = stats.mean
        result[RRKeys.builtinHzMedian] = stats.median
        logger.info("sampled \(stats.count, format: .decimal) frames — min=\(stats.min, format: .fixed(precision: 2)) max=\(stats.max, format: .fixed(precision: 2)) mean=\(stats.mean, format: .fixed(precision: 2))")
    } else {
        logger.warning("no samples captured within duration=\(duration, format: .fixed(precision: 3))s")
    }

    if let screen = screen(for: display) {
        let maxFPS = screen.maximumFramesPerSecond
        if maxFPS > 0 { result[RRKeys.builtinMaxFPS] = maxFPS }
    }

    var aggregateDict: [String: Any] = [
        "display_id": display,
        "cv": [
            "nominal_hz": (result[RRKeys.builtinHzNominal] as? Double) ?? 0.0,
            "actual_hz":  (result[RRKeys.builtinHzActual]  as? Double) ?? 0.0
        ]
    ]
    if let modeHz = result[RRKeys.builtinHzMode] {
        aggregateDict["mode_hz"] = modeHz
    }
    if let stats = computeStats(periods: samples) {
        aggregateDict["stats"] = [
            "count": stats.count,
            "min": stats.min,
            "max": stats.max,
            "mean": stats.mean,
            "median": stats.median
        ]
    }
    if let fps = result[RRKeys.builtinMaxFPS] {
        aggregateDict["max_fps"] = fps
    }
    result[RRKeys.builtinAggregate] = aggregateDict

    return result
}

// MARK: - 6. Main
// -------- Main --------
let args = CommandLine.arguments
let env = ProcessInfo.processInfo.environment
let duration: Double = {
    if CommandLine.arguments.count > 1, let v = Double(CommandLine.arguments[1]), v > 0 { return v }
    if let v = envDouble(env, key: RRConstants.envSampleSecs) { return v }
    return RRConstants.defaultSampleSeconds
}()

var out: [String: Any] = [:]
if let builtIn = builtinDisplayID() {
    out[RRKeys.builtinDisplayID] = builtIn
    for (k, v) in sampleRates(for: builtIn, duration: duration) { out[k] = v }
}

do {
    let data = try JSONSerialization.data(withJSONObject: out, options: [])
    FileHandle.standardOutput.write(data)
} catch {
    let errObj: [String: Any] = [RRKeys.error: RRKeys.json, RRKeys.message: String(describing: error)]
    if let data = try? JSONSerialization.data(withJSONObject: errObj, options: []) {
        FileHandle.standardOutput.write(data)
    } else {
        let fallback = "{\"\(RRKeys.error)\":\"\(RRKeys.json)\",\"\(RRKeys.message)\":\"serialization failed\"}".data(using: .utf8)!
        FileHandle.standardOutput.write(fallback)
    }
}