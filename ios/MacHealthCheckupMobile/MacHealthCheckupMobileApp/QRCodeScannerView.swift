import AVFoundation
import SwiftUI
import UIKit

struct QRCodeScannerView: UIViewControllerRepresentable {
    /**
     Summary
     Provide a native camera-backed QR code scanner for pairing import.

     Inputs
     onCode: Callback invoked with the scanned string payload.
     onCancel: Callback invoked when scanning is dismissed.

     Outputs
     A SwiftUI-compatible view controller representable.

     Side effects
     Uses the camera and starts a capture session.

     Error handling
     Reports camera availability errors via `onCode` with an empty string; callers should validate inputs.

     Ties to other methods
     Presented by `PairingView` to import URL and token quickly.

     Why this exists
     A premium pairing flow benefits from quick, low-friction imports without manual typing.
     */

    let onCode: (String) -> Void
    let onCancel: () -> Void

    func makeUIViewController(context: Context) -> ScannerViewController {
        /**
         Summary
         Construct the scanner view controller.

         Inputs
         context: Representable context.

         Outputs
         A `ScannerViewController`.

         Side effects
         None.

         Error handling
         None.

         Ties to other methods
         Called by SwiftUI.

         Why this exists
         Required by `UIViewControllerRepresentable`.
         */
        return ScannerViewController(onCode: onCode, onCancel: onCancel)
    }

    func updateUIViewController(_ uiViewController: ScannerViewController, context: Context) {
        /**
         Summary
         Update the controller as SwiftUI state changes.

         Inputs
         uiViewController: Scanner controller.
         context: Representable context.

         Outputs
         None.

         Side effects
         None.

         Error handling
         None.

         Ties to other methods
         Called by SwiftUI.

         Why this exists
         Required by `UIViewControllerRepresentable`.
         */
    }
}

final class ScannerViewController: UIViewController, @preconcurrency AVCaptureMetadataOutputObjectsDelegate {
    /**
     Summary
     Host an AVCaptureSession to scan QR codes with a live camera preview.

     Inputs
     onCode: Callback invoked with the decoded string payload.
     onCancel: Callback invoked when the user cancels.

     Outputs
     A view controller for QR scanning.

     Side effects
     Accesses the camera and runs capture sessions.

     Error handling
     Gracefully fails when camera configuration is unavailable.

     Ties to other methods
     Created by `QRCodeScannerView`.

     Why this exists
     Implements a polished pairing import experience without third-party dependencies.
     */

    private let session = AVCaptureSession()
    private var previewLayer: AVCaptureVideoPreviewLayer?

    private let onCode: (String) -> Void
    private let onCancel: () -> Void

    init(onCode: @escaping (String) -> Void, onCancel: @escaping () -> Void) {
        /**
         Summary
         Initialize the scanner view controller.

         Inputs
         onCode: Scan callback.
         onCancel: Cancel callback.

         Outputs
         None.

         Side effects
         None.

         Error handling
         None.

         Ties to other methods
         Used by `QRCodeScannerView.makeUIViewController`.

         Why this exists
         Keeps callbacks explicit for a predictable SwiftUI integration.
         */
        self.onCode = onCode
        self.onCancel = onCancel
        super.init(nibName: nil, bundle: nil)
    }

    @available(*, unavailable)
    required init?(coder: NSCoder) {
        fatalError("init(coder:) has not been implemented")
    }

    override func viewDidLoad() {
        /**
         Summary
         Configure camera capture session and UI chrome.

         Inputs
         None.

         Outputs
         None.

         Side effects
         Configures an AVCaptureSession and adds preview layer.

         Error handling
         Shows a basic fallback UI when camera capture cannot start.

         Ties to other methods
         Called by UIKit lifecycle.

         Why this exists
         Prepares the scanner to run immediately when presented.
         */
        super.viewDidLoad()
        view.backgroundColor = .black

        let cancel = UIButton(type: .system)
        cancel.setTitle("Cancel", for: .normal)
        cancel.tintColor = .white
        cancel.addTarget(self, action: #selector(_cancelTapped), for: .touchUpInside)
        cancel.translatesAutoresizingMaskIntoConstraints = false
        view.addSubview(cancel)
        NSLayoutConstraint.activate([
            cancel.topAnchor.constraint(equalTo: view.safeAreaLayoutGuide.topAnchor, constant: 12),
            cancel.leadingAnchor.constraint(equalTo: view.leadingAnchor, constant: 16),
        ])

        _configureSessionOrShowFailure()
    }

    override func viewWillAppear(_ animated: Bool) {
        /**
         Summary
         Start the capture session when the view appears.

         Inputs
         animated: Whether the transition is animated.

         Outputs
         None.

         Side effects
         Starts the capture session.

         Error handling
         None.

         Ties to other methods
         Called by UIKit lifecycle.

         Why this exists
         Avoids running the camera when the scanner is not visible.
         */
        super.viewWillAppear(animated)
        if !session.isRunning {
            session.startRunning()
        }
    }

    override func viewWillDisappear(_ animated: Bool) {
        /**
         Summary
         Stop the capture session when the view disappears.

         Inputs
         animated: Whether the transition is animated.

         Outputs
         None.

         Side effects
         Stops the capture session.

         Error handling
         None.

         Ties to other methods
         Called by UIKit lifecycle.

         Why this exists
         Prevents background camera usage after dismissal.
         */
        super.viewWillDisappear(animated)
        if session.isRunning {
            session.stopRunning()
        }
    }

    override func viewDidLayoutSubviews() {
        /**
         Summary
         Update preview layer layout to match the view bounds.

         Inputs
         None.

         Outputs
         None.

         Side effects
         Updates preview layer frame.

         Error handling
         None.

         Ties to other methods
         Called by UIKit layout.

         Why this exists
         Ensures camera preview fills the screen across device rotations.
         */
        super.viewDidLayoutSubviews()
        previewLayer?.frame = view.layer.bounds
    }

    func metadataOutput(_ output: AVCaptureMetadataOutput, didOutput metadataObjects: [AVMetadataObject], from connection: AVCaptureConnection) {
        /**
         Summary
         Receive QR metadata and forward the first decoded string to the caller.

         Inputs
         output: Metadata output.
         metadataObjects: Detected metadata objects.
         connection: Connection that produced the metadata.

         Outputs
         None.

         Side effects
         Stops scanning after receiving a code.

         Error handling
         Ignores non-QR and non-string metadata objects.

         Ties to other methods
         Called by AVCaptureMetadataOutputObjectsDelegate.

         Why this exists
         Implements the core QR scanning behavior for the pairing flow.
         */
        for obj in metadataObjects {
            guard let readable = obj as? AVMetadataMachineReadableCodeObject else { continue }
            guard readable.type == .qr else { continue }
            guard let value = readable.stringValue else { continue }
            session.stopRunning()
            onCode(value)
            return
        }
    }

    @objc private func _cancelTapped() {
        /**
         Summary
         Dismiss scanning when the user cancels.

         Inputs
         None.

         Outputs
         None.

         Side effects
         Stops the capture session and invokes the cancel callback.

         Error handling
         None.

         Ties to other methods
         Connected to the Cancel button target action.

         Why this exists
         Provides an explicit way to exit scanning without scanning a code.
         */
        if session.isRunning {
            session.stopRunning()
        }
        onCancel()
    }

    private func _configureSessionOrShowFailure() {
        /**
         Summary
         Configure capture input and metadata outputs for QR scanning.

         Inputs
         None.

         Outputs
         None.

         Side effects
         Configures AVCaptureSession and adds preview layer.

         Error handling
         Falls back to a simple label on failure.

         Ties to other methods
         Called by `viewDidLoad`.

         Why this exists
         Keeps the camera setup isolated and easy to audit.
         */
        guard let device = AVCaptureDevice.default(for: .video) else {
            _showFailure(message: "Camera unavailable.")
            return
        }
        guard let input = try? AVCaptureDeviceInput(device: device) else {
            _showFailure(message: "Camera access denied.")
            return
        }
        if session.canAddInput(input) {
            session.addInput(input)
        } else {
            _showFailure(message: "Failed to configure camera input.")
            return
        }

        let output = AVCaptureMetadataOutput()
        if session.canAddOutput(output) {
            session.addOutput(output)
        } else {
            _showFailure(message: "Failed to configure QR output.")
            return
        }
        output.setMetadataObjectsDelegate(self, queue: DispatchQueue.main)
        output.metadataObjectTypes = [.qr]

        let layer = AVCaptureVideoPreviewLayer(session: session)
        layer.videoGravity = .resizeAspectFill
        view.layer.insertSublayer(layer, at: 0)
        previewLayer = layer
    }

    private func _showFailure(message: String) {
        /**
         Summary
         Show a basic failure UI when scanning cannot be started.

         Inputs
         message: User-facing error message.

         Outputs
         None.

         Side effects
         Adds a label to the view hierarchy.

         Error handling
         None.

         Ties to other methods
         Called when session setup fails.

         Why this exists
         Keeps the UI responsive even if camera permissions are missing.
         */
        let label = UILabel()
        label.text = message
        label.textColor = .white
        label.numberOfLines = 0
        label.textAlignment = .center
        label.translatesAutoresizingMaskIntoConstraints = false
        view.addSubview(label)
        NSLayoutConstraint.activate([
            label.centerXAnchor.constraint(equalTo: view.centerXAnchor),
            label.centerYAnchor.constraint(equalTo: view.centerYAnchor),
            label.leadingAnchor.constraint(greaterThanOrEqualTo: view.leadingAnchor, constant: 20),
            label.trailingAnchor.constraint(lessThanOrEqualTo: view.trailingAnchor, constant: -20),
        ])
    }
}

