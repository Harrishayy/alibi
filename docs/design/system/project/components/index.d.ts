import type * as React from 'react';

/** Names in the Alibi icon set: 1.5px stroke on a 24 grid, round caps and joins, drawn in currentColor. */
export type IconName =
  | 'play' | 'pause' | 'stop' | 'plus' | 'check' | 'x' | 'camera' | 'laptop' | 'phone' | 'run' | 'heart'
  | 'moon' | 'calendar' | 'settings' | 'lens' | 'cup' | 'arrow-up' | 'arrow-right' | 'chevron-right'
  | 'chevron-down' | 'clock' | 'flag' | 'eye' | 'sparkle' | 'claw' | 'undo' | 'film';

/** What a sample (one look at the desk) showed. Always drawn as colour plus shape. */
export type SampleLabel = 'on_task' | 'idle' | 'phone' | 'off_task' | 'absent';

/** Pinch's held or looping states. */
export type PinchMood = 'idle' | 'focused' | 'listening' | 'thinking' | 'sleepy' | 'reading';
/** Pinch's one-shot clips; each returns to the current mood when it ends. */
export type PinchClip = 'hello' | 'sideeye' | 'nudge' | 'celebrate' | 'partial' | 'supportive' | 'surprise' | 'connected';

export interface ButtonProps extends Omit<React.ButtonHTMLAttributes<HTMLButtonElement>, 'children'> {
  /** `primary` (green fill, black text) at most once per view; `secondary` is the default; `ghost` is outlined; `quiet` is text only. */
  variant?: 'primary' | 'secondary' | 'ghost' | 'quiet';
  /** Height 28 / 36 / 44px. Default `md` (36px). */
  size?: 'sm' | 'md' | 'lg';
  /** An icon before the label (16px, 20px at `lg`). */
  icon?: IconName;
  /** Show only the icon; the button becomes square. Requires `ariaLabel`. */
  iconOnly?: boolean;
  /** Accessible name. Required when `iconOnly`. */
  ariaLabel?: string;
  /** The label: a verb first, sentence case ("Start session"). */
  children?: React.ReactNode;
}
/** The one button. Primary at most once per view. */
export declare function Button(props: ButtonProps): React.ReactElement;

export interface IconButtonProps extends Omit<React.ButtonHTMLAttributes<HTMLButtonElement>, 'children'> {
  /** The glyph to draw. */
  icon: IconName;
  /** Accessible name, always required ("Open setup"). */
  ariaLabel: string;
  /** Target 28 / 36 / 44px; icon 16 / 20 / 24px. Default `md`. */
  size?: 'sm' | 'md' | 'lg';
}
/** A quiet, icon-only control for toolbars, headers and dismiss buttons. */
export declare function IconButton(props: IconButtonProps): React.ReactElement;

export interface IconProps {
  /** Icon name from the set. Unknown names render nothing. */
  name: IconName;
  /** Rendered size in px: 16, 20 (default) or 24. */
  size?: number;
  /** When set, the icon is announced with this label; otherwise it is aria-hidden. */
  title?: string;
  className?: string;
}
/** A stroke icon in currentColor. `Alibi.Icon.names` lists the set. */
export declare const Icon: ((props: IconProps) => React.ReactElement | null) & { names: IconName[] };

export interface ChipProps extends Omit<React.ButtonHTMLAttributes<HTMLButtonElement>, 'children'> {
  /** Selected chips fill with `accent-wash` and set their text in `accent-ink`; exposed as aria-pressed. */
  selected?: boolean;
  /** An optional leading icon (16px). */
  icon?: IconName;
  /** An optional trailing keycap, such as "⌘1". */
  kbd?: string;
  /** One or two words: a habit or a filter. */
  children?: React.ReactNode;
}
/** A one-tap choice: habit chips under the composer, filters, the island's state picker. */
export declare function Chip(props: ChipProps): React.ReactElement;

export interface KbdProps extends React.HTMLAttributes<HTMLElement> {
  /** The key or chord as glyphs: "⌥⌘A", "↵", "esc", "⌘1", "/". */
  children?: React.ReactNode;
}
/** A keycap in the mono face. */
export declare function Kbd(props: KbdProps): React.ReactElement;

export interface ComposerProps {
  /** Placeholder and accessible label. Default "What are you about to do?". */
  placeholder?: string;
  /** Initial text; becomes controlled when `onChange` is passed too. */
  value?: string;
  /** Habit chips under the field, with ⌘1–⌘9 shortcuts; a click fills the field. */
  chips?: string[];
  /** Force the focused look (previews and screenshots). Real focus shows it anyway. */
  focused?: boolean;
  /** Called with the trimmed text on ↵ or the send button. Empty text never submits. */
  onSubmit?: (text: string) => void;
  /** Called with the raw text on every edit. */
  onChange?: (text: string) => void;
  className?: string;
}
/** The claim field: "What are you about to do?" plus a round green send button and habit chips. */
export declare function Composer(props: ComposerProps): React.ReactElement;

export interface CardProps extends React.HTMLAttributes<HTMLElement> {
  /** `default` is surface-1 with a hairline; `raised` is surface-2; `accent` is the green wash; `warn` is the red wash for bad news. */
  tone?: 'default' | 'raised' | 'accent' | 'warn';
  /** Inner padding 16 / 24 / 32px. Default `md` (24px, the web card padding). */
  padding?: 'sm' | 'md' | 'lg';
  /** The element to render. Default `div`; use `section` or `article` for landmarks. */
  as?: keyof JSX.IntrinsicElements;
  children?: React.ReactNode;
}
/** The one container: radius-md, a hairline edge, no shadow. */
export declare function Card(props: CardProps): React.ReactElement;

export interface StatusDotProps extends React.HTMLAttributes<HTMLSpanElement> {
  /** What the sample showed: ● on_task, ○ idle, ■ phone, hatched off_task, dashed absent. */
  label: SampleLabel;
  /** Mark size in px. Default 12. Under 16px the light theme draws it in the matching -ink token. */
  size?: number;
  /** Show the word beside the mark ("On task", "Idle", "Phone", "Off task", "Away"). Use in legends and lists. */
  text?: boolean;
}
/** A status mark that never relies on hue alone. */
export declare function StatusDot(props: StatusDotProps): React.ReactElement;

export interface SampleStripProps {
  /** Labels oldest to newest; pass the last 6. */
  labels: SampleLabel[];
  /** Cell height in px. Default 28 (square cells; 16:9 cells when `frames` is set). Keep it at 64 or under. */
  size?: number;
  /** Play the polaroid develop on the newest cell whenever the labels change. */
  develop?: boolean;
  /** Optional frame thumbnails (URLs), one per label, drawn under the mark. */
  frames?: string[];
  className?: string;
}
/** The last few samples of a live session, newest on the right. */
export declare function SampleStrip(props: SampleStripProps): React.ReactElement;

export interface VerdictPillProps extends React.HTMLAttributes<HTMLSpanElement> {
  /** ✓ Done, ◐ Partly or ✕ Slacked. */
  verdict: 'done' | 'partial' | 'slacked';
  /** On-task ratio 0–1, shown as a whole percentage. */
  ratio?: number;
}
/** The verdict as glyph, word and optional percentage on a 10% wash. */
export declare function VerdictPill(props: VerdictPillProps): React.ReactElement;

export interface MeterProps extends React.HTMLAttributes<HTMLDivElement> {
  /** On-task ratio 0–1. */
  value: number;
  /** Partial threshold and its tick. Default 0.4. */
  partAt?: number;
  /** Done threshold and its tick. Default 0.7. */
  doneAt?: number;
  /** Accessible label. Default "On task N%". */
  label?: string;
}
/** A horizontal on-task meter with ticks at the verdict thresholds; fills in done, partial or slacked colour. */
export declare function Meter(props: MeterProps): React.ReactElement;

export interface RingTimerProps extends React.HTMLAttributes<HTMLDivElement> {
  /** Elapsed fraction 0–1 of the session. */
  progress: number;
  /** The time to show in the centre, already formatted ("24:07"). */
  value: string;
  /** One short line under the value ("of 25 min"). */
  caption?: string;
  /** Diameter in px. Default 160 (web Now card). Under 88 the centre text is dropped: set the value beside it. */
  size?: number;
  /** Arc colour: `accent` (on task), `partial` (break, drifting), `warn` (overrun). */
  tone?: 'accent' | 'partial' | 'warn';
}
/** The live session ring; ticks once a second on its own once you update `progress`. */
export declare function RingTimer(props: RingTimerProps): React.ReactElement;

export interface StatProps extends React.HTMLAttributes<HTMLDivElement> {
  /** The number, formatted ("82%", "1h 52m", 6). Changed digits roll on spring-snappy. */
  value: React.ReactText;
  /** What it counts, sentence case ("On task"). */
  label: React.ReactNode;
  /** One quiet line of context ("Claimed 2h 10m"). */
  sub?: React.ReactNode;
}
/** One number with its label: the headline figure of a card. */
export declare function Stat(props: StatProps): React.ReactElement;

export interface StreakBadgeProps extends React.HTMLAttributes<HTMLSpanElement> {
  /** Days in a row. An increase bumps the badge and rolls the digit. */
  days: number;
  /** Freezes left this week; shown only when above 0. */
  freezes?: number;
}
/** The streak: claw glyph, rolling day count, freezes left. Never a flame. */
export declare function StreakBadge(props: StreakBadgeProps): React.ReactElement;

export interface PinchProps {
  /** The held or looping mood. Default `idle`. */
  mood?: PinchMood;
  /** Rendered size in px, from the ladder: 16, 20, 28, 32, 44, 56, 64, 96 (default), 160. */
  size?: number;
  /** A clip to play. It plays when this or `playKey` changes. */
  play?: PinchClip | null;
  /** Bump to replay the same clip. */
  playKey?: React.Key;
  /** Skip the engine's 90 s cooldown. Only for verdicts and the nudge after a side-eye. */
  force?: boolean;
  /** Palette: `dark` or `light` outline; omit to follow the page. */
  theme?: 'dark' | 'light';
  /** Hold still frames only (also forced by prefers-reduced-motion). */
  still?: boolean;
  className?: string;
}
/** Pinch, the green detective lobster, drawn live by the AlibiPinch engine. Decorative (aria-hidden). */
export declare function Pinch(props: PinchProps): React.ReactElement;

export interface PinchLineProps extends React.HTMLAttributes<HTMLDivElement> {
  /** Pinch's mood in the 20px avatar. Default `idle`. */
  mood?: PinchMood;
  /** The island-sized line (15px) instead of the web voice (20px). */
  compact?: boolean;
  /** Avatar palette; omit to follow the page. */
  theme?: 'dark' | 'light';
  /** One line in Alibi's voice, 12 words or fewer. Wrap only the cause noun in `<span className="al-cause">`. */
  children?: React.ReactNode;
}
/** A 20px Pinch and one sentence in Alibi's voice. */
export declare function PinchLine(props: PinchLineProps): React.ReactElement;

export type NotchIslandState = 'idle' | 'live' | 'peek' | 'expanded' | 'nudge' | 'verdict' | 'break';
export interface NotchIslandProps extends React.HTMLAttributes<HTMLDivElement> {
  /** idle 185×32 · live and break 277×32 · peek 289×36 · expanded 400×auto · nudge 400×auto · verdict 440×auto. */
  state: NotchIslandState;
  /** Override the panel width (expanded, nudge, verdict only). */
  width?: number;
  /** Left wing (16px Pinch) or, open, the header's left side ("ALIBI" wordmark and online dot). */
  leading?: React.ReactNode;
  /** Right wing (time left, "24m") or, open, the header's right side. */
  trailing?: React.ReactNode;
  /** Panel content for expanded, nudge and verdict; rendered in up to three tiers. */
  children?: React.ReactNode;
  /** Shake once on entering `nudge` (phone drift only). */
  shake?: boolean;
  /** Accessible region name. Default "Alibi island". */
  label?: string;
}
/** The Mac notch island as a web component: one black shape whose clip morphs between states. Always dark inside. */
export declare function NotchIsland(props: NotchIslandProps): React.ReactElement;

export interface ToastAction {
  label: string;
  variant?: ButtonProps['variant'];
  icon?: IconName;
  onClick?: () => void;
}
export interface ToastProps extends React.HTMLAttributes<HTMLDivElement> {
  /** `nudge` and `verdict` carry a PinchLine; `info` carries an optional icon and plain text. */
  kind: 'nudge' | 'verdict' | 'info';
  /** One short context line ("Drawing · 12 of 25 min"). */
  title: React.ReactNode;
  /** The message. For nudges and verdicts, Pinch's line. */
  children?: React.ReactNode;
  /** Up to three actions, as objects (rendered as small Buttons) or elements. The first object defaults to primary. */
  actions?: Array<ToastAction | React.ReactElement>;
  /** Shows a dismiss IconButton. */
  onClose?: () => void;
  /** Leading icon for `info`. */
  icon?: IconName;
  /** Pinch's mood in the avatar. */
  mood?: PinchMood;
}
/** A floating, polite notice: the web nudge, a verdict summary, a sync note. */
export declare function Toast(props: ToastProps): React.ReactElement;

declare global {
  interface Window {
    Alibi: {
      Button: typeof Button; IconButton: typeof IconButton; Icon: typeof Icon; Chip: typeof Chip; Kbd: typeof Kbd;
      Composer: typeof Composer; Card: typeof Card; StatusDot: typeof StatusDot; SampleStrip: typeof SampleStrip;
      VerdictPill: typeof VerdictPill; Meter: typeof Meter; RingTimer: typeof RingTimer; Stat: typeof Stat;
      StreakBadge: typeof StreakBadge; PinchLine: typeof PinchLine; Pinch: typeof Pinch; NotchIsland: typeof NotchIsland;
      Toast: typeof Toast;
    };
  }
}
