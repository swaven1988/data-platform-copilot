interface SkeletonProps {
    height?: number | string;
    width?: number | string;
    className?: string;
    lines?: number;
}

export default function Skeleton({ height = 16, width = "100%", className = "", lines = 1 }: SkeletonProps) {
    if (lines > 1) {
        return (
            <div className={`flex flex-col gap-2 ${className}`}>
                {Array.from({ length: lines }).map((_, i) => (
                    <div
                        key={i}
                        className="skeleton"
                        style={{ height, width: i === lines - 1 ? "60%" : width }}
                    />
                ))}
            </div>
        );
    }
    return (
        <div
            className={`skeleton ${className}`}
            style={{ height, width }}
        />
    );
}
