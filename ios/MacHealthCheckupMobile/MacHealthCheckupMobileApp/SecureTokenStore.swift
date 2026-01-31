import Foundation
import Security

enum SecureTokenStoreError: Error, CustomStringConvertible {
    case unexpectedStatus(file: StaticString, function: StaticString, message: String, status: OSStatus)
    case invalidTokenEncoding(file: StaticString, function: StaticString, message: String)

    var description: String {
        switch self {
        case let .unexpectedStatus(file, function, message, status):
            return "\(file) \(function): \(message) status=\(status)"
        case let .invalidTokenEncoding(file, function, message):
            return "\(file) \(function): \(message)"
        }
    }
}

protocol SecureTokenStore: Sendable {
    /**
     Summary
     Store and retrieve an authentication token securely.

     Inputs
     Implementations decide the persistence mechanism.

     Outputs
     String tokens for use with the agent API.

     Side effects
     Writes or deletes secure storage entries.

     Error handling
     Throws `SecureTokenStoreError` with actionable context.

     Ties to other methods
     Used by `MobileAppState` and settings views to persist pairing credentials.

     Why this exists
     Tokens must not be stored in UserDefaults or logs, and should survive app restarts.
     */

    func loadToken() throws -> String?
    func saveToken(_ token: String) throws
    func deleteToken() throws
}

struct KeychainSecureTokenStore: SecureTokenStore {
    /**
     Summary
     Keychain-backed token storage for iOS.

     Inputs
     service: Keychain service name.
     account: Keychain account identifier.

     Outputs
     Implements `SecureTokenStore`.

     Side effects
     Reads and writes to the system Keychain.

     Error handling
     Throws `SecureTokenStoreError` for non-success Keychain statuses.

     Ties to other methods
     Used by `MobileAppState` for persisted pairing credentials.

     Why this exists
     Keychain is the standard secure persistence mechanism for iOS secrets.
     */

    let service: String
    let account: String

    func loadToken() throws -> String? {
        /**
         Summary
         Load the current token from Keychain if present.

         Inputs
         None.

         Outputs
         Optional token string.

         Side effects
         None.

         Error handling
         Throws when Keychain returns a non-success status other than item-not-found.

         Ties to other methods
         Used when connecting with an empty token field.

         Why this exists
         Allows reusing an existing pairing token without retyping.
         */
        var query = _baseQuery()
        query[kSecReturnData as String] = true
        query[kSecMatchLimit as String] = kSecMatchLimitOne

        var item: CFTypeRef?
        let status = SecItemCopyMatching(query as CFDictionary, &item)
        if status == errSecItemNotFound {
            return nil
        }
        if status != errSecSuccess {
            throw SecureTokenStoreError.unexpectedStatus(
                file: #fileID,
                function: #function,
                message: "Keychain read failed",
                status: status
            )
        }
        guard let data = item as? Data else {
            throw SecureTokenStoreError.invalidTokenEncoding(
                file: #fileID,
                function: #function,
                message: "Keychain item data missing"
            )
        }
        guard let token = String(data: data, encoding: .utf8) else {
            throw SecureTokenStoreError.invalidTokenEncoding(
                file: #fileID,
                function: #function,
                message: "Keychain item was not UTF-8"
            )
        }
        return token
    }

    func saveToken(_ token: String) throws {
        /**
         Summary
         Save a token to Keychain, replacing any existing entry.

         Inputs
         token: Token string.

         Outputs
         None.

         Side effects
         Adds or updates a Keychain item.

         Error handling
         Throws when Keychain returns a non-success status.

         Ties to other methods
         Called when the user connects or updates credentials.

         Why this exists
         Ensures credentials are persisted securely across launches.
         */
        let trimmed = token.trimmingCharacters(in: .whitespacesAndNewlines)
        guard let data = trimmed.data(using: .utf8) else {
            throw SecureTokenStoreError.invalidTokenEncoding(
                file: #fileID,
                function: #function,
                message: "Token could not be encoded as UTF-8"
            )
        }

        var query = _baseQuery()
        let attributes: [String: Any] = [
            kSecValueData as String: data,
            kSecAttrAccessible as String: kSecAttrAccessibleAfterFirstUnlockThisDeviceOnly,
        ]

        let status = SecItemUpdate(query as CFDictionary, attributes as CFDictionary)
        if status == errSecItemNotFound {
            query.merge(attributes, uniquingKeysWith: { _, new in new })
            let addStatus = SecItemAdd(query as CFDictionary, nil)
            if addStatus != errSecSuccess {
                throw SecureTokenStoreError.unexpectedStatus(
                    file: #fileID,
                    function: #function,
                    message: "Keychain add failed",
                    status: addStatus
                )
            }
            return
        }
        if status != errSecSuccess {
            throw SecureTokenStoreError.unexpectedStatus(
                file: #fileID,
                function: #function,
                message: "Keychain update failed",
                status: status
            )
        }
    }

    func deleteToken() throws {
        /**
         Summary
         Remove the token from Keychain if present.

         Inputs
         None.

         Outputs
         None.

         Side effects
         Deletes a Keychain item.

         Error handling
         Throws when Keychain returns a non-success status other than item-not-found.

         Ties to other methods
         Called by disconnect and by settings reset.

         Why this exists
         Supports revocation and re-pairing without leaving stale secrets behind.
         */
        let status = SecItemDelete(_baseQuery() as CFDictionary)
        if status == errSecItemNotFound {
            return
        }
        if status != errSecSuccess {
            throw SecureTokenStoreError.unexpectedStatus(
                file: #fileID,
                function: #function,
                message: "Keychain delete failed",
                status: status
            )
        }
    }

    private func _baseQuery() -> [String: Any] {
        /**
         Summary
         Build a base Keychain query dictionary for the token item.

         Inputs
         None.

         Outputs
         Dictionary for Keychain calls.

         Side effects
         None.

         Error handling
         None.

         Ties to other methods
         Used by read, update, add, and delete operations.

         Why this exists
         Keeps Keychain identifiers centralized and consistent.
         */
        return [
            kSecClass as String: kSecClassGenericPassword,
            kSecAttrService as String: service,
            kSecAttrAccount as String: account,
        ]
    }
}

