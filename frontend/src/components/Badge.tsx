type Variant = "success" | "warning" | "error" | "info" | "neutral" | "accent";

interface BadgeProps {
    variant?: Variant;
    children: React.ReactNode;
    dot?: boolean;
    style?: React.CSSProperties;
    className?: string;
}

const variantMap: Record<Variant, string> = {
    success: "badge--success",
    warning: "badge--warning",
    error: "badge--error",
    info: "badge--info",
    neutral: "badge--neutral",
    accent: "badge--accent",
};

const dotMap: Record<Variant, string> = {
    success: "green",
    warning: "yellow",
    error: "red",
    info: "green",
    neutral: "gray",
    accent: "green",
};

export default function Badge({ variant = "neutral", children, dot, style, className = "" }: BadgeProps) {
    return (
        <span className={`badge ${variantMap[variant]} ${className}`} style={style}>
            {dot && <span className={`dot ${dotMap[variant]}`} style={{ width: 6, height: 6 }} />}
            {children}
        </span>
    );
}
