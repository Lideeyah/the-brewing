import Image from "next/image";

export function LogoMark({ size = 28 }: { size?: number }) {
  return (
    <Image
      src="/brewing-logo.svg"
      alt="Brewing"
      width={size}
      height={size}
      priority
      className="select-none"
    />
  );
}

export function Logo({ size = 28 }: { size?: number }) {
  return (
    <div className="flex items-center gap-2.5">
      <LogoMark size={size} />
      <span className="text-headline text-[15px] text-foreground">Brewing</span>
    </div>
  );
}
