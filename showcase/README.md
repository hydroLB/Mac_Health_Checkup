# Mac Health Checkup browser demonstration

Explore a Mac diagnostics interface without installing an agent. The readings are fictional sample data; this website does not inspect the visitor's machine. Open a diagnostic category, inspect its findings, and explore the report controls.

The React/TypeScript interface separates diagnostic presentation from the Python and Swift tools in the parent project. The implementation demonstrates how to organize machine-health findings and make their status understandable. Actual local checks require the desktop application described in [the parent README](../README.md).

## Run and build

Use Node 22.22 or newer in the Node 22 series and npm. From this directory:

```bash
npm ci
npm run dev
```

Open the local URL printed by the server. `npm run build` produces the Sites deployment build; `npm run lint` checks the source. No API key is needed for the browser demonstration. Hosting configuration is in `.openai/hosting.json`; publishing is a separate step.
