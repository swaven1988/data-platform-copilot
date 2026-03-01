/**
 * Approvals page UI for high-risk build approval lifecycle operations.
 *
 * This page provides grant, lookup, and revoke actions against approval APIs.
 * It does not implement batch analytics, pagination, or policy administration.
 */

import { useState } from "react";
import { CheckSquare, Search, Trash2, Plus } from "lucide-react";
import { toast } from "sonner";
import {
    createApproval,
    getApproval,
    listApprovals,
    revokeApproval,
    getApiErrorMessage,
    type ApprovalRecord,
} from "../lib/api";
import PageHeader from "../components/PageHeader";
import Card from "../components/Card";
import Badge from "../components/Badge";

export default function Approvals() {
    // Grant form
    const [grantJob, setGrantJob] = useState("");
    const [grantHash, setGrantHash] = useState("");
    const [grantApprover, setGrantApprover] = useState("");
    const [grantNotes, setGrantNotes] = useState("");
    const [granting, setGranting] = useState(false);
    const [granted, setGranted] = useState<ApprovalRecord | null>(null);

    // Lookup form
    const [lookupJob, setLookupJob] = useState("");
    const [lookupHash, setLookupHash] = useState("");
    const [looking, setLooking] = useState(false);
    const [found, setFound] = useState<ApprovalRecord | null>(null);
    const [revoking, setRevoking] = useState(false);

    // List panel
    const [listJob, setListJob] = useState("");
    const [listing, setListing] = useState(false);
    const [jobApprovals, setJobApprovals] = useState<ApprovalRecord[] | null>(null);

    const handleGrant = async () => {
        if (!grantJob.trim() || !grantHash.trim() || !grantApprover.trim()) {
            toast.error("Job name, plan hash, and approver are required.");
            return;
        }
        setGranting(true);
        try {
            const rec = await createApproval({
                job_name: grantJob.trim(),
                plan_hash: grantHash.trim(),
                approver: grantApprover.trim(),
                notes: grantNotes.trim() || undefined,
            });
            setGranted(rec);
            toast.success("Approval granted.");
        } catch (e: unknown) {
            toast.error(getApiErrorMessage(e, "Failed to grant approval."));
        } finally {
            setGranting(false);
        }
    };

    const handleLookup = async () => {
        if (!lookupJob.trim() || !lookupHash.trim()) {
            toast.error("Job name and plan hash required.");
            return;
        }
        setLooking(true);
        setFound(null);
        try {
            const rec = await getApproval(lookupJob.trim(), lookupHash.trim());
            setFound(rec);
        } catch (e: unknown) {
            toast.error(getApiErrorMessage(e, "Approval not found or expired."));
        } finally {
            setLooking(false);
        }
    };

    const handleRevoke = async (jobName: string, planHash: string) => {
        setRevoking(true);
        try {
            await revokeApproval(jobName, planHash);
            setFound(null);
            setGranted(prev => (prev?.job_name === jobName && prev?.plan_hash === planHash) ? null : prev);
            toast.success("Approval revoked.");
        } catch (e: unknown) {
            toast.error(getApiErrorMessage(e, "Failed to revoke approval."));
        } finally {
            setRevoking(false);
        }
    };

    const handleList = async () => {
        if (!listJob.trim()) {
            toast.error("Job name required.");
            return;
        }
        setListing(true);
        setJobApprovals(null);
        try {
            const recs = await listApprovals(listJob.trim());
            setJobApprovals(recs);
        } catch (e: unknown) {
            toast.error(getApiErrorMessage(e, "Failed to list approvals."));
        } finally {
            setListing(false);
        }
    };

    const inputStyle: React.CSSProperties = { width: "100%", marginBottom: "0.5rem" };

    return (
        <div>
            <PageHeader
                title="Build Approvals"
                subtitle="Grant and manage approvals for high-risk builds (risk score ≥ 0.70)"
            />

            <div style={{ display: "grid", gridTemplateColumns: "1fr 1fr", gap: "1.5rem", padding: "1.5rem" }}>

                {/* Grant Panel */}
                <Card
                    title="Grant Approval"
                    subtitle="Authorize a high-risk build to proceed"
                    actions={<CheckSquare size={18} />}
                >
                    <input
                        style={inputStyle}
                        placeholder="Job name"
                        value={grantJob}
                        onChange={e => setGrantJob(e.target.value)}
                    />
                    <input
                        style={inputStyle}
                        placeholder="Plan hash"
                        value={grantHash}
                        onChange={e => setGrantHash(e.target.value)}
                    />
                    <input
                        style={inputStyle}
                        placeholder="Your name (approver)"
                        value={grantApprover}
                        onChange={e => setGrantApprover(e.target.value)}
                    />
                    <textarea
                        style={{ ...inputStyle, height: "72px", resize: "vertical" }}
                        placeholder="Notes (optional)"
                        value={grantNotes}
                        onChange={e => setGrantNotes(e.target.value)}
                    />
                    <button
                        className="btn btn-primary"
                        onClick={handleGrant}
                        disabled={granting}
                        style={{ display: "flex", alignItems: "center", gap: "0.5rem" }}
                    >
                        <Plus size={14} />
                        {granting ? "Saving…" : "Grant Approval"}
                    </button>

                    {granted && (
                        <div style={{ marginTop: "1rem", padding: "0.75rem", background: "var(--color-success-bg, #f0fdf4)", borderRadius: "6px" }}>
                            <div style={{ display: "flex", alignItems: "center", gap: "0.5rem", marginBottom: "0.25rem" }}>
                                <Badge variant="success">Approved</Badge>
                                <span style={{ fontSize: "0.8rem", color: "#6b7280" }}>{granted.approved_at}</span>
                            </div>
                            <div style={{ fontSize: "0.85rem" }}>
                                <strong>{granted.job_name}</strong> / {granted.plan_hash}
                            </div>
                            <div style={{ fontSize: "0.8rem", color: "#6b7280" }}>Approver: {granted.approver}</div>
                            <button
                                className="btn btn-danger"
                                style={{ marginTop: "0.5rem", fontSize: "0.8rem", padding: "0.25rem 0.75rem", display: "flex", alignItems: "center", gap: "0.4rem" }}
                                onClick={() => handleRevoke(granted.job_name, granted.plan_hash)}
                                disabled={revoking}
                            >
                                <Trash2 size={12} /> Revoke
                            </button>
                        </div>
                    )}
                </Card>

                {/* Lookup Panel */}
                <Card
                    title="Look Up Approval"
                    subtitle="Check whether an approval exists and is valid"
                    actions={<Search size={18} />}
                >
                    <input
                        style={inputStyle}
                        placeholder="Job name"
                        value={lookupJob}
                        onChange={e => setLookupJob(e.target.value)}
                    />
                    <input
                        style={inputStyle}
                        placeholder="Plan hash"
                        value={lookupHash}
                        onChange={e => setLookupHash(e.target.value)}
                    />
                    <button
                        className="btn btn-secondary"
                        onClick={handleLookup}
                        disabled={looking}
                        style={{ display: "flex", alignItems: "center", gap: "0.5rem" }}
                    >
                        <Search size={14} />
                        {looking ? "Searching…" : "Look Up"}
                    </button>

                    {found && (
                        <div style={{ marginTop: "1rem", padding: "0.75rem", background: "var(--color-success-bg, #f0fdf4)", borderRadius: "6px" }}>
                            <div style={{ display: "flex", alignItems: "center", gap: "0.5rem", marginBottom: "0.25rem" }}>
                                <Badge variant="success" dot>Active</Badge>
                                <span style={{ fontSize: "0.8rem", color: "#6b7280" }}>{found.approved_at}</span>
                            </div>
                            <div style={{ fontSize: "0.85rem" }}>
                                <strong>{found.job_name}</strong> / {found.plan_hash}
                            </div>
                            <div style={{ fontSize: "0.8rem", color: "#6b7280" }}>Approver: {found.approver}</div>
                            {found.notes && <div style={{ fontSize: "0.8rem", color: "#6b7280" }}>Notes: {found.notes}</div>}
                            <button
                                className="btn btn-danger"
                                style={{ marginTop: "0.5rem", fontSize: "0.8rem", padding: "0.25rem 0.75rem", display: "flex", alignItems: "center", gap: "0.4rem" }}
                                onClick={() => handleRevoke(found.job_name, found.plan_hash)}
                                disabled={revoking}
                            >
                                <Trash2 size={12} /> Revoke
                            </button>
                        </div>
                    )}
                </Card>
            </div>

            {/* List Panel */}
            <div style={{ padding: "0 1.5rem 1.5rem" }}>
                <Card
                    title="All Approvals for Job"
                    subtitle="View all stored approvals for a job across all plan hashes"
                >
                    <div style={{ display: "flex", gap: "0.75rem", alignItems: "flex-end" }}>
                        <input
                            style={{ flex: 1 }}
                            placeholder="Job name"
                            value={listJob}
                            onChange={e => setListJob(e.target.value)}
                        />
                        <button
                            className="btn btn-secondary"
                            onClick={handleList}
                            disabled={listing}
                        >
                            {listing ? "Loading…" : "List"}
                        </button>
                    </div>

                    {jobApprovals !== null && (
                        <div style={{ marginTop: "1rem" }}>
                            {jobApprovals.length === 0 ? (
                                <p style={{ fontSize: "0.85rem", color: "#6b7280" }}>
                                    No approvals found for <strong>{listJob}</strong>.
                                </p>
                            ) : (
                                <table style={{ width: "100%", borderCollapse: "collapse", fontSize: "0.8rem" }}>
                                    <thead>
                                        <tr style={{ borderBottom: "1px solid #e5e7eb" }}>
                                            <th style={{ textAlign: "left", padding: "0.4rem 0.5rem" }}>Plan Hash</th>
                                            <th style={{ textAlign: "left", padding: "0.4rem 0.5rem" }}>Approver</th>
                                            <th style={{ textAlign: "left", padding: "0.4rem 0.5rem" }}>Approved At</th>
                                            <th style={{ textAlign: "left", padding: "0.4rem 0.5rem" }}>Action</th>
                                        </tr>
                                    </thead>
                                    <tbody>
                                        {jobApprovals.map(a => (
                                            <tr key={a.plan_hash} style={{ borderBottom: "1px solid #f3f4f6" }}>
                                                <td style={{ padding: "0.4rem 0.5rem", fontFamily: "monospace" }}>
                                                    {a.plan_hash.slice(0, 12)}…
                                                </td>
                                                <td style={{ padding: "0.4rem 0.5rem" }}>{a.approver}</td>
                                                <td style={{ padding: "0.4rem 0.5rem", color: "#6b7280" }}>
                                                    {a.approved_at}
                                                </td>
                                                <td style={{ padding: "0.4rem 0.5rem" }}>
                                                    <button
                                                        className="btn btn-danger"
                                                        style={{ fontSize: "0.75rem", padding: "0.2rem 0.5rem" }}
                                                        onClick={() => handleRevoke(a.job_name, a.plan_hash)
                                                            .then(() => handleList())
                                                        }
                                                        disabled={revoking}
                                                    >
                                                        Revoke
                                                    </button>
                                                </td>
                                            </tr>
                                        ))}
                                    </tbody>
                                </table>
                            )}
                        </div>
                    )}
                </Card>
            </div>
        </div>
    );
}
