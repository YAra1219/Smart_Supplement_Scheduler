export default function MeshGradientBackground() {
  return (
    <div className="fixed inset-0 overflow-hidden pointer-events-none z-0">
      <div
        className="absolute top-[-10%] right-[-10%] w-[300px] h-[300px] rounded-full bg-gradient-to-br from-purple-400/30 to-pink-400/30 blur-3xl animate-pulse"
        style={{ animationDuration: '4s' }}
      />
      <div
        className="absolute bottom-[10%] left-[-5%] w-[250px] h-[250px] rounded-full bg-gradient-to-tr from-blue-400/30 to-cyan-400/30 blur-3xl animate-pulse"
        style={{ animationDuration: '5s', animationDelay: '1s' }}
      />
      <div
        className="absolute top-[40%] left-[20%] w-[200px] h-[200px] rounded-full bg-gradient-to-bl from-indigo-400/20 to-purple-400/20 blur-3xl animate-pulse"
        style={{ animationDuration: '6s', animationDelay: '2s' }}
      />
    </div>
  );
}
