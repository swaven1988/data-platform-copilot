import { Toaster } from "sonner";

export default function Toast() {
    return (
        <Toaster
            position="bottom-right"
            theme="dark"
            toastOptions={{
                style: {
                    background: "var(--surface-2)",
                    border: "1px solid var(--border)",
                    color: "var(--text-primary)",
                    fontFamily: "Inter, system-ui, sans-serif",
                    fontSize: "13px",
                },
            }}
        />
    );
}
