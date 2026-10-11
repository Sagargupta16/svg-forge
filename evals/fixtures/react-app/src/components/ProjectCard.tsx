import { useMotionSetting } from "../settings/motion";

export type Project = Readonly<{ name: string; summary: string; tint: string }>;

/* Card grid: 280 to 420 px wide cards, dark canvas, 16:10 media slot on top. */
export function ProjectCard({ project }: Readonly<{ project: Project }>) {
  const motion = useMotionSetting();
  return (
    <article className="card" data-motion={motion}>
      <div className="card-media" style={{ aspectRatio: "16 / 10", background: "#0b1012" }}>
        {/* cover scene goes here */}
      </div>
      <h3>{project.name}</h3>
      <p>{project.summary}</p>
    </article>
  );
}
